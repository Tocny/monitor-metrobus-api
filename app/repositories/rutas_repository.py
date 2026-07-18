"""
Repository de rutas.

Acceso a datos de la tabla `rutas`.
Solo contiene consultas de lectura, ya que las rutas son datos
estáticos que se cargan una sola vez desde el GTFS y no se modifican
en tiempo de ejecución.

Dependencias:
    - asyncpg
    - app.entities.ruta.Ruta
"""

import asyncpg

from app.entities.ruta import Ruta

# Consultas SQL

_SQL_TODAS_LAS_RUTAS = """
    SELECT route_id, nombre_corto, nombre_largo, color, agencia
    FROM rutas
    ORDER BY nombre_corto, route_id
"""
# Obtiene todas las rutas disponibles, ordenadas por nombre corto
# y luego por route_id.


# Funciones.

async def get_todas_las_rutas(conn: asyncpg.Connection) -> list[Ruta]:
    """
    Obtiene todas las rutas disponibles en la base de datos.

    La consulta devuelve todas las rutas, independientemente de si
    tienen estaciones asociadas o no.
    
    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).

    Returns:
        Lista de objetos Ruta, ordenados por nombre_corto y route_id.
        Si no hay rutas, retorna lista vacía.

    Example:
        >>> rutas = await get_todas_las_rutas(conn)
        >>> for r in rutas:
        ...     print(f"{r.nombre_corto}: {r.nombre_largo}")
    """
    filas = await conn.fetch(_SQL_TODAS_LAS_RUTAS)
    return [Ruta(**dict(f)) for f in filas]