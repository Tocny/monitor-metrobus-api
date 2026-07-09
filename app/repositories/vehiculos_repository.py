"""
Repository de vehiculos.

Solo acceso a datos -- no contiene logica de negocio.
"""

from datetime import datetime, timezone

import asyncpg

from app.entities.vehiculo import VehiculoActual

_SQL_GET_VEHICULO = """
    SELECT vehicle_id, label, route_id, lat, lon, velocidad,
           feed_timestamp, estacion_actual_id, actualizado_en
    FROM vehiculos_actuales
    WHERE vehicle_id = $1
"""

_SQL_UPSERT_VEHICULO = """
    INSERT INTO vehiculos_actuales
        (vehicle_id, label, route_id, lat, lon, velocidad,
         feed_timestamp, estacion_actual_id, actualizado_en)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    ON CONFLICT (vehicle_id) DO UPDATE SET
        label              = EXCLUDED.label,
        route_id           = EXCLUDED.route_id,
        lat                = EXCLUDED.lat,
        lon                = EXCLUDED.lon,
        velocidad          = EXCLUDED.velocidad,
        feed_timestamp     = EXCLUDED.feed_timestamp,
        estacion_actual_id = EXCLUDED.estacion_actual_id,
        actualizado_en     = EXCLUDED.actualizado_en
"""


async def get_vehiculo(
    conn: asyncpg.Connection, vehicle_id: str
) -> VehiculoActual | None:
    fila = await conn.fetchrow(_SQL_GET_VEHICULO, vehicle_id)
    if fila is None:
        return None
    return VehiculoActual(**dict(fila))


async def upsert_vehiculo(
    conn: asyncpg.Connection, vehiculo: VehiculoActual
) -> None:
    await conn.execute(
        _SQL_UPSERT_VEHICULO,
        vehiculo.vehicle_id,
        vehiculo.label,
        vehiculo.route_id,
        vehiculo.lat,
        vehiculo.lon,
        vehiculo.velocidad,
        vehiculo.feed_timestamp,
        vehiculo.estacion_actual_id,
        vehiculo.actualizado_en or datetime.now(timezone.utc),
    )