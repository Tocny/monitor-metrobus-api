"""
Politica de retencion para pasos_registrados, via asyncpg (sin ORM).

Manda llamar a podar_pasos_registrados() despues de cada insercion
nueva en el worker de polling (Fase 3). Usa una window function de
PostgreSQL para borrar, POR CADA combinacion (estacion_id, route_id),
todo lo que sobre del limite N -- asi una estacion muy transitada
nunca desplaza el historial de las demas.
"""

import asyncpg

MAX_PASOS_POR_ESTACION_RUTA = 10

_QUERY_PODA = """
    DELETE FROM pasos_registrados
    WHERE id IN (
        SELECT id FROM (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY estacion_id, route_id
                    ORDER BY detectado_en DESC
                ) AS posicion
            FROM pasos_registrados
        ) ranked
        WHERE posicion > $1
    )
"""


async def podar_pasos_registrados(
    conn: asyncpg.Connection, limite: int = MAX_PASOS_POR_ESTACION_RUTA
) -> int:
    """
    Borra los registros de pasos_registrados que excedan el limite,
    manteniendo siempre los mas recientes por (estacion_id, route_id).
    Devuelve el numero de filas eliminadas.
    """
    resultado = await conn.execute(_QUERY_PODA, limite)
    # asyncpg devuelve algo como "DELETE 7" -- extraemos el numero.
    return int(resultado.split()[-1])
