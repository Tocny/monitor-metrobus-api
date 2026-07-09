"""
Service: worker de polling (Fase 3).

Responsabilidad: orquestar el ciclo de monitoreo cada 30 segundos.
No contiene SQL -- delega todo acceso a datos a los repositories.
No sabe de HTTP -- delega la obtencion del feed a metrobus_client.
"""

import asyncio
import logging
from datetime import datetime, timezone

import asyncpg

from app.core.config import get_settings
from app.db.session import get_pool
from app.entities.paso import PasoRegistrado
from app.entities.vehiculo import VehiculoActual
from app.repositories.estaciones_repository import get_estaciones_de_ruta
from app.repositories.pasos_repository import insertar_paso
from app.repositories.vehiculos_repository import get_vehiculo, upsert_vehiculo
from app.services.geo import distancia_metros
from app.services.metrobus_client import obtener_vehiculos_actuales

logger = logging.getLogger(__name__)
settings = get_settings()

_worker_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Logica de negocio: deteccion de pasos
# ---------------------------------------------------------------------------

async def _detectar_paso(
    conn: asyncpg.Connection,
    vehiculo_nuevo: VehiculoActual,
    cache_estaciones: dict,
) -> None:
    """
    Compara la posicion nueva del vehiculo contra las estaciones de su
    ruta. Si cruzo de FUERA a DENTRO del radio de una estacion,
    registra el paso.
    """
    route_id = vehiculo_nuevo.route_id
    if not route_id:
        return

    if route_id not in cache_estaciones:
        cache_estaciones[route_id] = await get_estaciones_de_ruta(conn, route_id)

    estaciones = cache_estaciones[route_id]
    if not estaciones:
        return

    # Estacion en cuyo radio se encuentra el vehiculo ahora.
    estacion_actual_id = None
    for est in estaciones:
        if distancia_metros(
            vehiculo_nuevo.lat, vehiculo_nuevo.lon, est.lat, est.lon
        ) <= settings.station_radius_meters:
            estacion_actual_id = est.stop_id
            break

    vehiculo_nuevo.estacion_actual_id = estacion_actual_id

    # Estado anterior del vehiculo en la BD.
    vehiculo_anterior = await get_vehiculo(conn, vehiculo_nuevo.vehicle_id)
    estacion_anterior_id = vehiculo_anterior.estacion_actual_id if vehiculo_anterior else None

    # Transicion FUERA -> DENTRO: paso confirmado.
    if estacion_actual_id and estacion_anterior_id != estacion_actual_id:
        paso = PasoRegistrado(
            estacion_id=estacion_actual_id,
            route_id=route_id,
            vehicle_id=vehiculo_nuevo.vehicle_id,
            label=vehiculo_nuevo.label,
            detectado_en=datetime.fromtimestamp(
                vehiculo_nuevo.feed_timestamp, tz=timezone.utc
            ),
        )
        await insertar_paso(conn, paso)
        logger.info(
            "Paso confirmado: vehiculo=%s label=%s estacion=%s ruta=%s",
            vehiculo_nuevo.vehicle_id,
            vehiculo_nuevo.label,
            estacion_actual_id,
            route_id,
        )


# ---------------------------------------------------------------------------
# Ciclo principal
# ---------------------------------------------------------------------------

async def _ciclo(pool: asyncpg.Pool) -> None:
    try:
        vehiculos = await obtener_vehiculos_actuales()
    except Exception as e:
        logger.error("Error al obtener el feed: %s", e)
        return

    ahora = datetime.now(timezone.utc)
    cache_estaciones: dict = {}

    async with pool.acquire() as conn:
        for v in vehiculos:
            try:
                vehiculo_actual = VehiculoActual(
                    vehicle_id=v.vehicle_id,
                    label=v.label,
                    route_id=v.route_id,
                    lat=v.lat,
                    lon=v.lon,
                    velocidad=v.velocidad,
                    feed_timestamp=v.timestamp,
                    actualizado_en=ahora,
                )
                await _detectar_paso(conn, vehiculo_actual, cache_estaciones)
                await upsert_vehiculo(conn, vehiculo_actual)
            except Exception as e:
                logger.error("Error procesando vehiculo %s: %s", v.vehicle_id, e)

    logger.debug("Ciclo completado: %d vehiculos procesados.", len(vehiculos))


async def _loop() -> None:
    pool = await get_pool()
    logger.info(
        "Worker iniciado. Intervalo: %ds, radio: %dm.",
        settings.polling_interval_seconds,
        settings.station_radius_meters,
    )
    while True:
        await _ciclo(pool)
        await asyncio.sleep(settings.polling_interval_seconds)


# ---------------------------------------------------------------------------
# API publica (llamada desde main.py lifespan)
# ---------------------------------------------------------------------------

async def iniciar_worker() -> None:
    global _worker_task
    _worker_task = asyncio.create_task(_loop(), name="worker-polling")


async def detener_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
    logger.info("Worker detenido.")