"""
Service: cálculo de frecuencias de paso.

Maneja el recálculo periódico de frecuencias promedio de paso de
rutas en estaciones. 
Este servicio no ejecuta SQL directamente; delega en el repositorio
`frecuencias_repository` para la persistencia y el cálculo.

Dependencias:
    - asyncpg
    - app.repositories.frecuencias_repository
"""

import asyncpg

from app.repositories.frecuencias_repository import calcular_y_guardar_frecuencias


async def recalcular_frecuencias(
    conn: asyncpg.Connection,
    intervalo_analisis_minutos: int,
) -> None:
    """
    Recalcula y persiste las frecuencias promedio para todas las
    combinaciones estación+ruta con datos suficientes.

    Esta función es el punto de entrada del servicio de frecuencias
    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).
        intervalo_analisis_minutos: Ventana de tiempo (en minutos) hacia
            atrás desde el momento actual que se considera para el cálculo

    Returns:
        None

    Note:
        - El repositorio se encarga del UPSERT en la tabla 'frecuencias'.

    Example:
        >>> async with asyncpg.create_pool(...) as pool:
        ...     async with pool.acquire() as conn:
        ...         await recalcular_frecuencias(conn, 1440)
    """
    await calcular_y_guardar_frecuencias(conn, intervalo_analisis_minutos)