"""
Repository de estaciones.

Solo acceso a datos -- no contiene logica de negocio.
"""

import asyncpg

from app.entities.estacion import Estacion

_SQL_ESTACIONES_DE_RUTA = """
    SELECT e.stop_id, e.nombre, e.lat, e.lon
    FROM estaciones e
    JOIN ruta_estaciones re ON re.stop_id = e.stop_id
    WHERE re.route_id = $1
"""

_SQL_ESTACION_CERCANA = """
    SELECT stop_id, nombre, lat, lon,
           ST_Distance(
               ubicacion,
               ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
           ) AS distancia_metros
    FROM estaciones
    ORDER BY ubicacion <-> ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
    LIMIT 1
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