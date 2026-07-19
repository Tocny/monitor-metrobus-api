"""
Service: pasos registrados.

Capa intermedia entre el controller y el repository para gestionar
la información de pasos de vehículos por estaciones.

provee:
    - el último paso registrado para una estación y ruta específicas.
    - el historial de los últimos N pasos para una estación y ruta.

De momento se delega como pura consulta al repositorio pero...
Potencialmente podriamos:
    - Calcular el tiempo transcurrido desde el último paso.
    - Estimar la frecuencia de paso promedio.
    - Calcular metricas de paso por hora del día o día de la semana.

Dependencias:
    - asyncpg 
    - app.repositories.pasos_repository
    - app.entities.paso
"""

import asyncpg

from app.entities.paso import PasoRegistrado
from app.repositories.pasos_repository import get_ultimo_paso, get_ultimos_pasos


async def obtener_ultimo_paso(
    conn: asyncpg.Connection,
    estacion_id: str,
    route_id: str,
) -> PasoRegistrado | None:
    """
    Obtiene el paso más reciente para una estación y ruta específicas.

    Esta función es utilizada principalmente por el endpoint de estado
    de una estación para mostrar cuándo fue la última vez que un
    vehículo pasó por esa estación en una ruta.

    Args:
        conn: Conexión activa a PostgreSQL.
        estacion_id: Identificador de la estación.
        route_id: Identificador de la ruta.

    Returns:
        Objeto PasoRegistrado con el último paso, o None si no hay

    Example:
        >>> from app.db.session import get_pool
        >>> async with get_pool().acquire() as conn:
        ...     ultimo = await obtener_ultimo_paso(conn, "fa078a", "19429")
        ...     if ultimo:
        ...         print(f"Último paso: {ultimo.detectado_en} por vehículo {ultimo.label}")
        ...     else:
        ...         print("No hay pasos registrados para esta ruta.")
    """
    return await get_ultimo_paso(conn, estacion_id, route_id)


async def obtener_ultimos_pasos(
    conn: asyncpg.Connection,
    estacion_id: str,
    route_id: str,
) -> list[PasoRegistrado]:
    """
    Obtiene los últimos N pasos (hasta 10) para una estación y ruta específicas.

    Esta función es útil para mostrar el historial reciente de pasos en
    o para calcular metricas de frecuencia.

    El número máximo de pasos devueltos está definido por la constante
    MAX_PASOS_POR_ESTACION_RUTA en el repositorio (max 10),

    Args:
        conn: Conexión activa a PostgreSQL.
        estacion_id: Identificador de la estación.
        route_id: Identificador de la ruta.

    Returns:
        Lista de objetos PasoRegistrado.

    Example:
        >>> from app.db.session import get_pool
        >>> async with get_pool().acquire() as conn:
        ...     pasos = await obtener_ultimos_pasos(conn, "fa078a", "19429")
        ...     for paso in pasos:
        ...         print(f"{paso.detectado_en}: vehículo {paso.label}")
        2026-07-18 12:30:45: vehículo 1203
        2026-07-18 12:28:15: vehículo 1204
        2026-07-18 12:25:30: vehículo 1203
    """
    return await get_ultimos_pasos(conn, estacion_id, route_id)