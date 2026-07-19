"""
Service: worker de polling.

Contiene el ciclo de monitoreo cada 30 segundos para
detectar el paso de vehículos por estaciones y actualizar la última
posición conocida de cada vehículo.

Flujo principal:
    1. Obtiene posiciones de autobuses desde el feed (vía metrobus_client).
    2. Para cada autobús, calcula si está dentro del radio de una estación
       de su ruta (usando distancia_metros).
    3. Si el autobús entró en el radio (y antes no estaba), registra un "paso"
       en la tabla pasos_registrados (vía pasos_repository).
    4. Actualiza la última posición conocida del autobús en vehiculos_actuales
       (vía vehiculos_repository).
    5. Espera 30 segundos y repite.

El worker se ejecuta como una tarea asíncrona en segundo plano.

Dependencias:
    - app.services.metrobus_client: Descarga y parsea el feed GTFS-RT.
    - app.repositories.*: Operaciones de base de datos.
    - app.services.geo: Cálculo de distancias Haversine.
    - app.core.config: Configuración.
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
"""
Referencia a la tarea asíncrona del worker, para poder cancelarla
limpiamente al apagar la aplicación.
"""


# Lógica de detección de pasos

async def _detectar_paso(
    conn: asyncpg.Connection,
    vehiculo_nuevo: VehiculoActual,
    cache_estaciones: dict,
) -> None:
    """
    Detecta si un vehículo ha pasado por una estación.

    Compara la posición actual del vehículo contra las estaciones de su ruta.
    Si el vehículo entró en el radio de una estación y antes no estaba en
    ninguna, registra un paso en la base de datos.

    La lógica se basa en la transición FUERA -> DENTRO del radio de la
    estación para evitar registrar pasos duplicados si el vehículo se
    queda detenido en la estación.

    Args:
        conn: Conexión activa a PostgreSQL.
        vehiculo_nuevo: Vehículo con la posición actual.
        cache_estaciones: Diccionario en memoria para cachear las estaciones
            de cada ruta.

    Raises:
        ValueError: Si el vehículo no tiene route_id (se maneja).
        DatabaseError: Si falla la consulta a la base de datos .

    Afecta:
        - Actualiza vehiculo_nuevo.estacion_actual_id con la estación
          encontrada (o None si está fuera de toda estación).
        - Inserta un registro en pasos_registrados si detecta un paso.
    """
    route_id = vehiculo_nuevo.route_id
    if not route_id:
        return

    # Cargar estaciones de la ruta
    if route_id not in cache_estaciones:
        cache_estaciones[route_id] = await get_estaciones_de_ruta(conn, route_id)

    estaciones = cache_estaciones[route_id]
    if not estaciones:
        return

    # Encontrar la estación más cercana dentro del radio
    estacion_actual_id = None
    for est in estaciones:
        if distancia_metros(
            vehiculo_nuevo.lat, vehiculo_nuevo.lon, est.lat, est.lon
        ) <= settings.station_radius_meters:
            estacion_actual_id = est.stop_id
            break

    vehiculo_nuevo.estacion_actual_id = estacion_actual_id

    # Obtener estado anterior del vehículo
    vehiculo_anterior = await get_vehiculo(conn, vehiculo_nuevo.vehicle_id)
    estacion_anterior_id = vehiculo_anterior.estacion_actual_id if vehiculo_anterior else None

    # Transición FUERA -> DENTRO: paso confirmado
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


# Ciclo principal

async def _ciclo(pool: asyncpg.Pool) -> None:
    """
    Ejecuta una iteración completa del worker (descarga y procesamiento).

    Obtiene los vehículos del feed, actualiza su posición y detecta pasos.
    Si se registra un error, se aborta el ciclo (no se procesan vehículos
    hasta la siguiente iteración).

    Args:
        pool: Pool de conexiones a PostgreSQL.
    """
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
    """
    Bucle infinito que ejecuta _ciclo() cada polling_interval_seconds.

    Se ejecuta como una tarea asíncrona en segundo plano. La función
    iniciar_worker() la lanza, y detener_worker() la termina.

    El bucle captura excepciones a nivel de ciclo, pero si _ciclo() falla
    de forma inesperada, el error se loguea y el bucle continúa.
    """
    pool = await get_pool()
    logger.info(
        "Worker iniciado. Intervalo: %ds, radio: %dm.",
        settings.polling_interval_seconds,
        settings.station_radius_meters,
    )
    while True:
        await _ciclo(pool)
        await asyncio.sleep(settings.polling_interval_seconds)


# API

async def iniciar_worker() -> None:
    """
    Inicia el worker de polling como una tarea asíncrona en segundo plano.

    Esta función se llama desde el lifespan (en main) cuando
    la aplicación arranca. La tarea se ejecuta en el event loop principal.

    La tarea se almacena en la variable global _worker_task para poder
    ser cancelada al apagar la aplicación.
    """
    global _worker_task
    _worker_task = asyncio.create_task(_loop(), name="worker-polling")


async def detener_worker() -> None:
    """
    Detiene el worker de polling.

    Cancela la tarea asíncrona del worker y espera a que termine.

    Esta función se llama desde el lifespan (en main) cuando
    la aplicación se apaga, asegurando que no queden tareas en segundo
    plano colgadas.
    """
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None
    logger.info("Worker detenido.")