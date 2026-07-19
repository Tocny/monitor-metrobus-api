"""
Service: Mapa.

Capa intermedia entre el controller y los repositories para preparar
los datos necesarios para el mapa (estaciones, vehículos, rutas y
sus trazos).

Obtiene:
    - estaciones para mostrar en el mapa.
    - vehículos en tiempo real (última posición conocida).
    - rutas con sus shapes (trazos geométricos) para dibujar las líneas en el mapa.
→ Service (este módulo) → Repositories (acceso a datos)

Dependencias:
    - asyncpg 
    - app.repositories.* 
    - app.entities.*
"""

import asyncpg

from app.entities.estacion import Estacion
from app.entities.ruta import Ruta
from app.entities.shape import ShapePunto
from app.entities.vehiculo import VehiculoActual
from app.repositories.estaciones_repository import get_estacion_cercana
from app.repositories.rutas_repository import get_todas_las_rutas
from app.repositories.shapes_repository import get_todos_los_puntos
from app.repositories.vehiculos_repository import get_todos_vehiculos


async def obtener_estaciones_para_mapa(
    conn: asyncpg.Connection,
) -> list[Estacion]:
    """
    Obtiene todas las estaciones disponibles para mostrar en el mapa.

    Esta función consulta directamente la tabla estaciones y devuelve
    todas las estaciones con sus coordenadas. Es utilizada por el
    endpoint de mapa para dibujar los marcadores de estaciones.

    Args:
        conn: Conexión activa a PostgreSQL.

    Returns:
        Lista de objetos Estacion con todos los atributos..

    Example:
        >>> estaciones = await obtener_estaciones_para_mapa(conn)
        >>> for e in estaciones[:3]:
        ...     print(f"{e.nombre}: ({e.lat}, {e.lon})")
        'Potrero: (19.476608, -132.652085)'
        'Circuito L1: (19.462622, -143.867237)'
        'San Simón: (19.459519, -146.438168)'
    """
    filas = await conn.fetch("SELECT stop_id, nombre, lat, lon FROM estaciones")
    return [Estacion(**dict(f)) for f in filas]


async def obtener_vehiculos_para_mapa(
    conn: asyncpg.Connection,
) -> list[VehiculoActual]:
    """
    Obtiene la última posición conocida de todos los vehículos activos.

    Esta función delega en el repositorio de vehículos para obtener
    la información más reciente de cada vehículo.

    Args:
        conn: Conexión activa a PostgreSQL.

    Returns:
        Lista de objetos VehiculoActual con la última posición conocida
        de cada vehículo.

    Example:
        >>> vehiculos = await obtener_vehiculos_para_mapa(conn)
        >>> for v in vehiculos[:3]:
        ...     print(f"Autobús {v.label}: ({v.lat}, {v.lon})")
        'Autobús 1203: (19.467312, -99.140939)'
        'Autobús 1204: (19.467537, -99.140775)'
        'Autobús 1205: (19.467686, -99.140616)'
    """
    return await get_todos_vehiculos(conn)


async def obtener_rutas_para_mapa(
    conn: asyncpg.Connection,
) -> tuple[list[Ruta], dict[str, list[ShapePunto]]]:
    """
    Obtiene todas las rutas y sus shapes.

    Esta función combina dos consultas en una sola operación para que
    el controller pueda construir el GeoJSON completo de todas las
    líneas, sin necesidad de hacer múltiples llamadas al repositorio.

    La estructura de retorno es:
        - Una lista de Rutas
        - Un diccionario donde cada clave es un route_id y el valor
          es la lista de puntos que forman su trazado

    Args:
        conn: Conexión activa a PostgreSQL.

    Returns:
        Tupla con:
            - Lista de objetos Ruta.
            - Diccionario {route_id: [ShapePunto, ...]} 
              con los puntos de cada ruta.

    Example:
        >>> rutas, shapes = await obtener_rutas_para_mapa(conn)
        >>> for ruta in rutas[:3]:
        ...     puntos = shapes.get(ruta.route_id, [])
        ...     print(f"Ruta {ruta.nombre_corto}: {len(puntos)} puntos")
        'Ruta 1: 234 puntos'
        'Ruta 2: 189 puntos'
        'Ruta 3: 156 puntos'
    """
    rutas = await get_todas_las_rutas(conn)
    shapes = await get_todos_los_puntos(conn)
    return rutas, shapes