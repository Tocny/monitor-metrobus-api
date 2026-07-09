"""
Repository de pasos registrados.

Incluye la logica de poda (retencion) porque es una operacion de
datos pura -- no hay logica de negocio involucrada.
Reemplaza app/services/retencion.py.
"""

import asyncpg

from app.entities.paso import PasoRegistrado

MAX_PASOS_POR_ESTACION_RUTA = 10

_SQL_INSERTAR_PASO = """
    INSERT INTO pasos_registrados
        (estacion_id, route_id, vehicle_id, label, detectado_en)
    VALUES ($1, $2, $3, $4, $5)
"""

_SQL_ULTIMO_PASO = """
    SELECT id, estacion_id, route_id, vehicle_id, label, detectado_en
    FROM pasos_registrados
    WHERE estacion_id = $1 AND route_id = $2
    ORDER BY detectado_en DESC
    LIMIT 1
"""

_SQL_PODAR = """
    DELETE FROM pasos_registrados
    WHERE id IN (
        SELECT id FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY estacion_id, route_id
                       ORDER BY detectado_en DESC
                   ) AS posicion
            FROM pasos_registrados
        ) ranked
        WHERE posicion > $1
    )
"""


async def insertar_paso(
    conn: asyncpg.Connection, paso: PasoRegistrado
) -> None:
    await conn.execute(
        _SQL_INSERTAR_PASO,
        paso.estacion_id,
        paso.route_id,
        paso.vehicle_id,
        paso.label,
        paso.detectado_en,
    )
    await podar_pasos(conn)


async def get_ultimo_paso(
    conn: asyncpg.Connection, estacion_id: str, route_id: str
) -> PasoRegistrado | None:
    fila = await conn.fetchrow(_SQL_ULTIMO_PASO, estacion_id, route_id)
    if fila is None:
        return None
    return PasoRegistrado(**dict(fila))


async def podar_pasos(
    conn: asyncpg.Connection,
    limite: int = MAX_PASOS_POR_ESTACION_RUTA,
) -> None:
    await conn.execute(_SQL_PODAR, limite)