"""
Repository de frecuencias.

Dependencias:
    - asyncpg
    - app.entities.frecuencia
"""

import asyncpg

from app.entities.frecuencia import FrecuenciaRutaEstacion


# Consultas SQL

_SQL_CALCULAR_FRECUENCIAS = """
    WITH diffs AS (
        SELECT
            estacion_id,
            route_id,
            EXTRACT(EPOCH FROM (
                detectado_en
                - LAG(detectado_en) OVER (
                    PARTITION BY estacion_id, route_id
                    ORDER BY detectado_en
                )
            )) / 60.0 AS diff_minutos
        FROM pasos_registrados
        WHERE detectado_en > NOW() - ($1 * INTERVAL '1 minute')
    )
    INSERT INTO frecuencias (estacion_id, route_id, intervalo_minutos, calculado_en)
    SELECT
        estacion_id,
        route_id,
        AVG(diff_minutos),
        NOW()
    FROM diffs
    WHERE diff_minutos IS NOT NULL
    GROUP BY estacion_id, route_id
    ON CONFLICT (estacion_id, route_id) DO UPDATE SET
        intervalo_minutos = EXCLUDED.intervalo_minutos,
        calculado_en      = EXCLUDED.calculado_en
"""
# 1. Calcular y guardar frecuencias de todas las combinaciones
#
# Calcula el intervalo promedio entre pasos consecutivos para TODAS las
# combinaciones (estacion_id, route_id) con al menos 2 pasos en la ventana
# de análisis (parámetro $1 en minutos).

#    1. 
#      - Para cada (estacion_id, route_id), ordena los pasos por
#        detectado_en.
#      - LAG(detectado_en) obtiene la fecha del paso anterior.
#      - EXTRACT(EPOCH FROM ...)/60.0 calcula la diferencia en minutos.
#      - Solo considera pasos dentro de la ventana temporal
#        (detectado_en > NOW() - ($1 * INTERVAL '1 minute')).
#   2. 
#      - Filtra las diferencias no nulas.
#      - Agrupa por (estacion_id, route_id) y calcula AVG.
#      - Usa NOW() como fecha de cálculo.
#   3. ON CONFLICT actualiza las columnas si la combinación ya existe.



_SQL_GET_FRECUENCIA = """
    SELECT estacion_id, route_id, intervalo_minutos, calculado_en
    FROM frecuencias
    WHERE estacion_id = $1 AND route_id = $2
"""
# 2. Obtener una frecuencia específica para una combinación estación-ruta
#
# Consulta a la tabla `frecuencias` para obtener el intervalo
# promedio y la fecha de cálculo.
#
#   1. Filtra por estacion_id y route_id.
#   2. Devuelve las cuatro columnas necesarias para construir la entidad.
#


# Funciones

async def calcular_y_guardar_frecuencias(
    conn: asyncpg.Connection,
    intervalo_analisis_minutos: int,
) -> None:
    """
    Recalcula las frecuencias promedio para todas las combinaciones
    estación+ruta y las persiste en la tabla 'frecuencias'.

    La función ejecuta la consulta SQL que calcula el intervalo promedio
    de los pasos dentro de la ventana de tiempo especificada, y luego
    inserta o actualiza (ON CONFLICT) la fila correspondiente para cada
    combinación.

    Args:
        conn: Conexión activa a PostgreSQL.
        intervalo_analisis_minutos: Ventana de tiempo (en minutos) hacia
            atrás desde el momento actual que se considera para el cálculo

    Returns:
        None

    Note:
        - Las combinaciones con 0 o 1 pasos en la ventana quedan con
          `intervalo_minutos = NULL`.

    Example:
        >>> async with asyncpg.create_pool(...) as pool:
        ...     async with pool.acquire() as conn:
        ...         await calcular_y_guardar_frecuencias(conn, 1440)
    """
    await conn.execute(_SQL_CALCULAR_FRECUENCIAS, intervalo_analisis_minutos)


async def get_frecuencia(
    conn: asyncpg.Connection,
    estacion_id: str,
    route_id: str,
) -> FrecuenciaRutaEstacion | None:
    """
    Obtiene la frecuencia promedio de una ruta en una estación específica.

    Realiza una consulta a la tabla 'frecuencias' para obtener
    el intervalo promedio y la fecha de cálculo correspondientes a la
    (estacion_id, route_id) solicitada.

    Args:
        conn: Conexión activa a PostgreSQL.
        estacion_id: Identificador de la estación (stop_id).
        route_id: Identificador de la ruta (route_id).

    Returns:
        Una instancia de 'FrecuenciaRutaEstacion' si existe la combinación
        en la tabla, o `None` si no se encuentra.

    Example:
        >>> async with asyncpg.create_pool(...) as pool:
        ...     async with pool.acquire() as conn:
        ...         frec = await get_frecuencia(conn, "TERM001", "RUTA42")
        ...         if frec:
        ...             print(f"Intervalo: {frec.intervalo_minutos} min")
        ...         else:
        ...             print("No hay frecuencia calculada para esta ruta")
    """
    fila = await conn.fetchrow(_SQL_GET_FRECUENCIA, estacion_id, route_id)
    if fila is None:
        return None
    return FrecuenciaRutaEstacion(**dict(fila))