"""
Repository de shapes (trazos geometricos de rutas).

Solo acceso a datos -- no contiene logica de negocio.
"""

import asyncpg

from app.entities.shape import ShapePunto

_SQL_PUNTOS_POR_RUTA = """
    SELECT route_id, secuencia, lat, lon
    FROM shapes
    WHERE route_id = $1
    ORDER BY secuencia
"""

_SQL_TODAS_LAS_RUTAS = """
    SELECT route_id, secuencia, lat, lon
    FROM shapes
    ORDER BY route_id, secuencia
"""


async def get_puntos_por_ruta(
    conn: asyncpg.Connection, route_id: str
) -> list[ShapePunto]:
    filas = await conn.fetch(_SQL_PUNTOS_POR_RUTA, route_id)
    return [ShapePunto(**dict(f)) for f in filas]


async def get_todos_los_puntos(
    conn: asyncpg.Connection,
) -> dict[str, list[ShapePunto]]:
    """
    Devuelve todos los shapes agrupados por route_id.
    Usado por el endpoint /mapa/rutas para construir el GeoJSON
    completo de todas las lineas en una sola consulta.
    """
    filas = await conn.fetch(_SQL_TODAS_LAS_RUTAS)
    resultado: dict[str, list[ShapePunto]] = {}
    for f in filas:
        punto = ShapePunto(**dict(f))
        if punto.route_id not in resultado:
            resultado[punto.route_id] = []
        resultado[punto.route_id].append(punto)
    return resultado