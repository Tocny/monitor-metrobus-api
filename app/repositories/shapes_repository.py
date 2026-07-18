"""
Repository de shapes (trazos geométricos de rutas).

Acceso a datos de la tabla `shapes`, que contiene los
puntos que forman las líneas de cada ruta. Estos puntos se utilizan
para dibujar las rutas en el mapa.

Los shapes son datos estáticos que se cargan una sola vez desde el GTFS.

Dependencias:
    - asyncpg
    - app.entities.shape.ShapePunto
"""

import asyncpg

from app.entities.shape import ShapePunto

# Consultas SQL (preparadas)

_SQL_PUNTOS_POR_RUTA = """
    SELECT route_id, secuencia, lat, lon
    FROM shapes
    WHERE route_id = $1
    ORDER BY secuencia
"""
# Obtiene todos los puntos de una ruta específica, ordenados por secuencia.

_SQL_TODAS_LAS_RUTAS = """
    SELECT route_id, secuencia, lat, lon
    FROM shapes
    ORDER BY route_id, secuencia
"""
# Obtiene todos los puntos de todas las rutas, ordenados por route_id
# y secuencia. Se usa para construir un GeoJSON completo de todas las
# líneas en una sola consulta.


# Funciones.

async def get_puntos_por_ruta(
    conn: asyncpg.Connection,
    route_id: str,
) -> list[ShapePunto]:
    """
    Obtiene todos los puntos de una ruta específica, en orden de secuencia.

    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).
        route_id: Identificador de la ruta (ej. "19429").

    Returns:
        Lista de objetos ShapePunto, ordenados por secuencia ascendente.
        Si la ruta no tiene puntos (o no existe), retorna lista vacía.

    Example:
        >>> puntos = await get_puntos_por_ruta(conn, "19429")
        >>> for p in puntos[:3]:
        ...     print(f"({p.lat}, {p.lon})")
        (19.467312, -99.140939)
        (19.467537, -99.140775)
        (19.467686, -99.140616)
    """
    filas = await conn.fetch(_SQL_PUNTOS_POR_RUTA, route_id)
    return [ShapePunto(**dict(f)) for f in filas]


async def get_todos_los_puntos(
    conn: asyncpg.Connection,
) -> dict[str, list[ShapePunto]]:
    """
    Devuelve todos los puntos de todas las rutas, agrupados por route_id.

    Esta función está hecha para construir el GeoJSON completo de
    todas las líneas en una sola consulta a la base de datos, evitando
    hacer N consultas. Es util para cuando necesitemos dibujar todas las rutas.

    Args:
        conn: Conexión activa a PostgreSQL.

    Returns:
        Diccionario donde las claves son route_id y los valores son listas
        de ShapePunto (ya ordenados por secuencia).

    Example:
        >>> shapes = await get_todos_los_puntos(conn)
        >>> for route_id, puntos in shapes.items():
        ...     print(f"Ruta {route_id}: {len(puntos)} puntos")
        Ruta 19429: 49 puntos
        Ruta 19430: 49 puntos
        ...
    """
    filas = await conn.fetch(_SQL_TODAS_LAS_RUTAS)
    resultado: dict[str, list[ShapePunto]] = {}
    for f in filas:
        punto = ShapePunto(**dict(f))
        if punto.route_id not in resultado:
            resultado[punto.route_id] = []
        resultado[punto.route_id].append(punto)
    return resultado