"""
Repository de pasos registrados.

Acceso a datos de la tabla `pasos_registrados`.
Incluye la lógica de poda (retención).
No hay lógica de negocio real ( simplemente
mantener la tabla acotada para que no crezca tanto).

La poda se ejecuta automáticamente después de cada inserción,
manteniendo un máximo de `MAX_PASOS_POR_ESTACION_RUTA` registros por
cada combinación (estacion_id, route_id). Esto asegura que la tabla
nunca crezca sin control.

La idea es que no me salga caro alojarla en la nube jaja.
Además esto es por si en un futuro se expande el comportamiento del proyecto
en realidad los 10 registros solo son por un historial que podriamos usar para métricas.

Dependencias:
    - asyncpg
    - app.entities.paso.PasoRegistrado
"""

import asyncpg

from app.entities.paso import PasoRegistrado


MAX_PASOS_POR_ESTACION_RUTA: int = 10
"""
Número máximo de pasos que se conservan por cada combinación de
(estacion_id, route_id). Los pasos más antiguos se eliminan
automáticamente después de cada inserción.
"""

# Consultas SQL (preparadas)

_SQL_INSERTAR_PASO = """
    INSERT INTO pasos_registrados
        (estacion_id, route_id, vehicle_id, label, detectado_en)
    VALUES ($1, $2, $3, $4, $5)
"""
# Inserción de un nuevo paso.

_SQL_ULTIMO_PASO = """
    SELECT id, estacion_id, route_id, vehicle_id, label, detectado_en
    FROM pasos_registrados
    WHERE estacion_id = $1 AND route_id = $2
    ORDER BY detectado_en DESC
    LIMIT 1
"""
# Obtiene el paso más reciente para una estación y ruta específicas.
# Útil para mostrar "último paso" en el frontend o para detectar si
# un vehículo ya pasó recientemente.

_SQL_ULTIMOS_PASOS = """
    SELECT id, estacion_id, route_id, vehicle_id, label, detectado_en
    FROM pasos_registrados
    WHERE estacion_id = $1 AND route_id = $2
    ORDER BY detectado_en DESC
    LIMIT $3
"""
# Obtiene los N últimos pasos para una estación y ruta.
# Se usa para mostrar historial reciente.

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
# Elimina los pasos excedentes (los más antiguos) para cada combinación
# de (estacion_id, route_id), manteniendo solo los `limite` más recientes.
# Usa ROW_NUMBER() con PARTITION BY para numerar los pasos por grupo,
# y luego elimina aquellos con número > limite.
# Esto se ejecuta después de cada inserción para mantener la tabla acotada.


# Funciones.

async def insertar_paso(
    conn: asyncpg.Connection,
    paso: PasoRegistrado,
) -> None:
    """
    Inserta un nuevo paso en la base de datos y luego ejecuta la poda.

    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).
        paso: Objeto PasoRegistrado con los datos del paso a insertar.

    Raises:
        asyncpg.exceptions.PostgresError: Si falla la inserción.
        (la poda se ejecuta en la misma transacción)

    Example:
        >>> paso = PasoRegistrado(
        ...     estacion_id="fa078a",
        ...     route_id="19429",
        ...     vehicle_id="69379",
        ...     label="1203",
        ...     detectado_en=datetime.now(timezone.utc)
        ... )
        >>> await insertar_paso(conn, paso)
    """
    await conn.execute(
        _SQL_INSERTAR_PASO,
        paso.estacion_id,
        paso.route_id,
        paso.vehicle_id,
        paso.label,
        paso.detectado_en,
    )
    # Después de insertar, eliminar los pasos excedentes
    await podar_pasos(conn)


async def get_ultimo_paso(
    conn: asyncpg.Connection,
    estacion_id: str,
    route_id: str,
) -> PasoRegistrado | None:
    """
    Obtiene el paso más reciente para una estación y ruta específicas.

    Args:
        conn: Conexión activa a PostgreSQL.
        estacion_id: Identificador de la estación (stop_id).
        route_id: Identificador de la ruta.

    Returns:
        Objeto PasoRegistrado con el último paso, o None si no hay
        ningún paso registrado para esa combinación.

    Example:
        >>> paso = await get_ultimo_paso(conn, "fa078a", "19429")
        >>> if paso:
        ...     print(f"Último paso: {paso.detectado_en}")
    """
    fila = await conn.fetchrow(_SQL_ULTIMO_PASO, estacion_id, route_id)
    if fila is None:
        return None
    return PasoRegistrado(**dict(fila))


async def get_ultimos_pasos(
    conn: asyncpg.Connection,
    estacion_id: str,
    route_id: str,
    limite: int = MAX_PASOS_POR_ESTACION_RUTA,
) -> list[PasoRegistrado]:
    """
    Obtiene los últimos N pasos para una estación y ruta específicas.

    Args:
        conn: Conexión activa a PostgreSQL.
        estacion_id: Identificador de la estación (stop_id).
        route_id: Identificador de la ruta.
        limite: Número máximo de pasos a recuperar.
                Por defecto usa MAX_PASOS_POR_ESTACION_RUTA (10).

    Returns:
        Lista de objetos PasoRegistrado, ordenados del más reciente al
        más antiguo.

    Example:
        >>> pasos = await get_ultimos_pasos(conn, "fa078a", "19429", 5)
        >>> for p in pasos:
        ...     print(p.detectado_en, p.vehicle_id)
    """
    filas = await conn.fetch(_SQL_ULTIMOS_PASOS, estacion_id, route_id, limite)
    return [PasoRegistrado(**dict(f)) for f in filas]


async def podar_pasos(
    conn: asyncpg.Connection,
    limite: int = MAX_PASOS_POR_ESTACION_RUTA,
) -> None:
    """
    Elimina los pasos excedentes para cada combinación de estación+ruta,
    manteniendo solo los `limite` más recientes.

    Esta función se llama automáticamente después de cada inserción.

    Args:
        conn: Conexión activa a PostgreSQL.
        limite: Número máximo de pasos a conservar por cada grupo.
                Por defecto usa MAX_PASOS_POR_ESTACION_RUTA (10).

    Raises:
        asyncpg.exceptions.PostgresError: Si falla la eliminación.

    Example:
        # Forzar una poda manual (útil después de cargas masivas)
        >>> await podar_pasos(conn, 5)  # Dejar solo 5 pasos por grupo
    """
    await conn.execute(_SQL_PODAR, limite)