"""
Repository de vehículos.

Acceso a datos de la tabla `vehiculos_actuales`, que
almacena la última posición conocida de cada vehículo. La tabla se
actualiza constantemente (cada 30 segundos) mediante UPSERT, por lo
que nunca crece más allá del número de vehículos activos (800,900).

Dependencias:
    - asyncpg 
    - app.entities.vehiculo.VehiculoActual
"""

from datetime import datetime, timezone

import asyncpg

from app.entities.vehiculo import VehiculoActual

# Consultas SQL (preparadas)

_SQL_GET_VEHICULO = """
    SELECT vehicle_id, label, route_id, lat, lon, velocidad,
           feed_timestamp, estacion_actual_id, actualizado_en
    FROM vehiculos_actuales
    WHERE vehicle_id = $1
"""
# Obtiene la última posición conocida de un vehículo por su ID.

_SQL_GET_TODOS = """
    SELECT vehicle_id, label, route_id, lat, lon, velocidad,
           feed_timestamp, estacion_actual_id, actualizado_en
    FROM vehiculos_actuales
"""
# Obtiene las posiciones de todos los vehículos activos.

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
# UPSERT: si el vehículo ya existe, se actualiza su posición; si no,
# se inserta un nuevo registro. Esto asegura que la tabla nunca crezca
# y siempre contenga la información más reciente de cada vehículo.
# Se usa ON CONFLICT (vehicle_id), para resolver el conflicto.


# Funciones.

async def get_vehiculo(
    conn: asyncpg.Connection,
    vehicle_id: str,
) -> VehiculoActual | None:
    """
    Obtiene la última posición conocida de un vehículo por su ID.

    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).
        vehicle_id: Identificador del vehículo (vehicle.vehicle.id
                    del feed GTFS-RT, estable en el tiempo).

    Returns:
        Objeto VehiculoActual con la última posición, o None si el
        vehículo no está en la base de datos (nunca se ha visto).

    Example:
        >>> vehiculo = await get_vehiculo(conn, "69379")
        >>> if vehiculo:
        ...     print(f"Autobús {vehiculo.label} en ({vehiculo.lat}, {vehiculo.lon})")
    """
    fila = await conn.fetchrow(_SQL_GET_VEHICULO, vehicle_id)
    if fila is None:
        return None
    return VehiculoActual(**dict(fila))


async def get_todos_vehiculos(
    conn: asyncpg.Connection,
) -> list[VehiculoActual]:
    """
    Obtiene las posiciones de todos los vehículos activos.

    Útil para mostrar todos los autobuses en el mapa.

    Args:
        conn: Conexión activa a PostgreSQL.

    Returns:
        Lista de objetos VehiculoActual. Si no hay vehículos activos,
        retorna lista vacía.

    Example:
        >>> vehiculos = await get_todos_vehiculos(conn)
        >>> print(f"Autobuses activos: {len(vehiculos)}")
        Autobuses activos: 829
    """
    filas = await conn.fetch(_SQL_GET_TODOS)
    return [VehiculoActual(**dict(f)) for f in filas]


async def upsert_vehiculo(
    conn: asyncpg.Connection,
    vehiculo: VehiculoActual,
) -> None:
    """
    Inserta o actualiza la posición de un vehículo en la base de datos.

    Si el vehículo ya existe (mismo vehicle_id), se actualiza su
    posición y timestamp. Si no existe, se inserta un nuevo registro.

    Args:
        conn: Conexión activa a PostgreSQL.
        vehiculo: Objeto VehiculoActual con los datos a guardar.

    Raises:
        asyncpg.exceptions.PostgresError: Si falla la operación.

    Example:
        >>> vehiculo = VehiculoActual(
        ...     vehicle_id="69379",
        ...     label="1203",
        ...     route_id="19429",
        ...     lat=19.467312,
        ...     lon=-99.140939,
        ...     velocidad=0.0,
        ...     feed_timestamp=1781755570,
        ...     estacion_actual_id="fa078a",
        ...     actualizado_en=datetime.now(timezone.utc)
        ... )
        >>> await upsert_vehiculo(conn, vehiculo)
    """
    # Si actualizado_en no está definido, usar el timestamp actual
    actualizado = vehiculo.actualizado_en or datetime.now(timezone.utc)

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
        actualizado,
    )