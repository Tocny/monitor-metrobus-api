"""
Repository de rutas.

Solo acceso a datos -- no contiene logica de negocio.
"""

import asyncpg

from app.entities.ruta import Ruta

_SQL_TODAS_LAS_RUTAS = """
    SELECT route_id, nombre_corto, nombre_largo, color, agencia
    FROM rutas
    ORDER BY nombre_corto, route_id
"""


async def get_todas_las_rutas(conn: asyncpg.Connection) -> list[Ruta]:
    filas = await conn.fetch(_SQL_TODAS_LAS_RUTAS)
    return [Ruta(**dict(f)) for f in filas]