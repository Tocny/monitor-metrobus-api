"""
Repository de estaciones.

Solo acceso a datos -- no contiene logica de negocio.
"""

import asyncpg

from app.entities.estacion import (
    Estacion,
    EstadoEstacion,
    RutaConUltimoPaso,
    UltimoPasoResumen,
)

_SQL_ESTACIONES_DE_RUTA = """
    SELECT e.stop_id, e.nombre, e.lat, e.lon
    FROM estaciones e
    JOIN ruta_estaciones re ON re.stop_id = e.stop_id
    WHERE re.route_id = $1
"""

_SQL_ESTACION_CERCANA = """
    SELECT stop_id, nombre, lat, lon
    FROM estaciones
    ORDER BY ubicacion <-> ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
    LIMIT 1
"""

# LATERAL JOIN: por cada ruta distinta que pasa por la estacion,
# obtiene el ultimo paso registrado en una sola consulta.
_SQL_ESTADO_ESTACION = """
    SELECT
        e.stop_id,
        e.nombre,
        r.route_id,
        r.nombre_corto,
        r.nombre_largo,
        r.color,
        p.vehicle_id,
        p.label      AS vehiculo_label,
        p.detectado_en
    FROM estaciones e
    CROSS JOIN (
        SELECT DISTINCT route_id
        FROM ruta_estaciones
        WHERE stop_id = $1
    ) re
    JOIN rutas r ON r.route_id = re.route_id
    LEFT JOIN LATERAL (
        SELECT vehicle_id, label, detectado_en
        FROM pasos_registrados
        WHERE estacion_id = $1 AND route_id = re.route_id
        ORDER BY detectado_en DESC
        LIMIT 1
    ) p ON true
    WHERE e.stop_id = $1
    ORDER BY r.nombre_corto, r.route_id
"""


async def get_estaciones_de_ruta(
    conn: asyncpg.Connection, route_id: str
) -> list[Estacion]:
    filas = await conn.fetch(_SQL_ESTACIONES_DE_RUTA, route_id)
    return [Estacion(**dict(f)) for f in filas]


async def get_estacion_cercana(
    conn: asyncpg.Connection, lat: float, lon: float
) -> Estacion | None:
    fila = await conn.fetchrow(_SQL_ESTACION_CERCANA, lat, lon)
    if fila is None:
        return None
    return Estacion(**dict(fila))


async def get_estado_estacion(
    conn: asyncpg.Connection, stop_id: str
) -> EstadoEstacion | None:
    filas = await conn.fetch(_SQL_ESTADO_ESTACION, stop_id)
    if not filas:
        return None

    nombre = filas[0]["nombre"]
    rutas = []
    for f in filas:
        ultimo_paso = None
        if f["vehicle_id"] is not None:
            ultimo_paso = UltimoPasoResumen(
                vehicle_id=f["vehicle_id"],
                label=f["vehiculo_label"],
                detectado_en=f["detectado_en"],
            )
        rutas.append(RutaConUltimoPaso(
            route_id=f["route_id"],
            nombre_corto=f["nombre_corto"],
            nombre_largo=f["nombre_largo"],
            color=f"#{f['color']}" if f["color"] else None,
            ultimo_paso=ultimo_paso,
        ))

    return EstadoEstacion(stop_id=stop_id, nombre=nombre, rutas=rutas)