"""
Service: Estaciones.

Capa intermedia entre el controller y el repositorio. Su responsabilidad
es orquestar la lógica de negocio relacionada con estaciones, delegando
el acceso a datos al repositorio correspondiente.

Dependencias:
    - asyncpg
    - app.repositories.estaciones_repository 
    - app.entities.estacion
"""

import asyncpg

from app.entities.estacion import Estacion, EstadoEstacion
from app.repositories.estaciones_repository import (
    get_estacion_cercana,
    get_estado_estacion,
)


async def obtener_estacion_cercana(
    conn: asyncpg.Connection,
    lat: float,
    lon: float,
) -> Estacion | None:
    """
    Obtiene la estación más cercana a un punto geográfico.

    Delega directamente en el repositorio, que utiliza el índice
    GIST para encontrar la estación más cercana.

    Args:
        conn: Conexión activa a PostgreSQL.
        lat: Latitud del punto en grados decimales.
        lon: Longitud del punto en grados decimales.

    Returns:
        Objeto Estacion de la más cercana, o None.

    Example:
        >>> from app.db.session import get_pool
        >>> async with get_pool().acquire() as conn:
        ...     estacion = await obtener_estacion_cercana(conn, 19.4326, -99.1332)
        ...     print(estacion.nombre)
        'Zócalo'
    """
    return await get_estacion_cercana(conn, lat, lon)


async def obtener_estado_estacion(
    conn: asyncpg.Connection,
    stop_id: str,
) -> EstadoEstacion | None:
    """
    Obtiene el estado completo de una estación.

    Esto incluye el nombre de la estación y, para cada ruta que pasa
    por ella, el último paso registrado. La información se
    obtiene en una sola consulta.

    Args:
        conn: Conexión activa a PostgreSQL.
        stop_id: Identificador de la estación.

    Returns:
        Objeto EstadoEstacion con el nombre y las rutas con su último paso,
        o None si la estación no existe.

    Example:
        >>> from app.db.session import get_pool
        >>> async with get_pool().acquire() as conn:
        ...     estado = await obtener_estado_estacion(conn, "fa078a")
        ...     if estado:
        ...         print(f"Estación: {estado.nombre}")
        ...         for ruta in estado.rutas:
        ...             if ruta.ultimo_paso:
        ...                 print(f"  {ruta.nombre_corto}: último paso {ruta.ultimo_paso.detectado_en}")
    """
    return await get_estado_estacion(conn, stop_id)