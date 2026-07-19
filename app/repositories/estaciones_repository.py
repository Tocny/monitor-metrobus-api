"""
Repository de estaciones.

Acceso a datos de estaciones y su estado. 
No contiene lógica de negocio; ejecuta consultas SQL y 
convierte los resultados en entidades.

funciones sql utilizadas:
    - `ORDER BY ubicacion <-> ST_MakePoint(...)::geography` : usa el
      índice GIST para encontrar la estación más cercana.
    - `LATERAL JOIN` : permite, para cada ruta que pasa por una
      estación, obtener el último paso registrado en una sola consulta.

Dependencias:
    - asyncpg
    - app.entities.estacion
"""

import asyncpg

from app.entities.estacion import (
    Estacion,
    EstadoEstacion,
    RutaConUltimoPaso,
    UltimoPasoResumen,
)

#Consultas SQL.

_SQL_ESTACIONES_DE_RUTA = """
    SELECT e.stop_id, e.nombre, e.lat, e.lon
    FROM estaciones e
    JOIN ruta_estaciones re ON re.stop_id = e.stop_id
    WHERE re.route_id = $1
    ORDER BY re.orden
"""
# 1. Obtener estaciones de una ruta en orden
# Devuelve todas las estaciones que pertenecen a una ruta.
#
#   1. JOIN entre estaciones y ruta_estaciones para filtrar por route_id.
#   2. ORDER BY re.orden asegura que las estaciones vengan en la secuencia correcta según el GTFS.
#

_SQL_ESTACION_CERCANA = """
    SELECT stop_id, nombre, lat, lon
    FROM estaciones
    ORDER BY ubicacion <-> ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
    LIMIT 1
"""
# 2. Estación más cercana a un punto geográfico (KNN)
# 
# Encuentra la estación más cercana a unas coordenadas dadas, usando el índice GIST
# 
#   1. ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography convierte las
#     coordenadas (lon, lat) en un punto geográfico.
#   2. El operador <-> (KNN) ordena las estaciones
#     por distancia al punto usando el índice GIST.
#   3. LIMIT 1 devuelve solo la más cercana.
#

_SQL_ESTADO_ESTACION = """
    SELECT
        e.stop_id,
        e.nombre,
        r.route_id,
        r.nombre_corto,
        r.nombre_largo,
        r.color,
        p.vehicle_id,
        p.label      AS vehiculo_label,
        p.detectado_en
    FROM estaciones e
    CROSS JOIN (
        SELECT DISTINCT route_id
        FROM ruta_estaciones
        WHERE stop_id = $1
    ) re
    JOIN rutas r ON r.route_id = re.route_id
    LEFT JOIN LATERAL (
        SELECT vehicle_id, label, detectado_en
        FROM pasos_registrados
        WHERE estacion_id = $1 AND route_id = re.route_id
        ORDER BY detectado_en DESC
        LIMIT 1
    ) p ON true
    WHERE e.stop_id = $1
    ORDER BY r.nombre_corto, r.route_id
"""
# 3. Estado completo de una estación (nombre, rutas, último paso)

# Obtiene, en una sola consulta, el nombre de la estación,
# todas las rutas que pasan por ella, y el último paso registrado en
# cada una de esas rutas.
# 
#   1. FROM estaciones e : partimos de la estación que nos interesa.
#   2. CROSS JOIN ( SELECT DISTINCT route_id FROM ruta_estaciones WHERE stop_id = $1 ) re
#      Obtiene todas las rutas distintas que pasan por esta estación.
#   3. JOIN rutas r ON r.route_id = re.route_id
#      Trae los datos de cada ruta (nombre, color, etc.).
#   4. LEFT JOIN LATERAL ( ... ) p ON true
#      - Para CADA ruta, ejecuta una subconsulta que obtiene el ÚLTIMO
#        paso registrado en esa estación para esa ruta (ordenando por
#        detectado_en DESC y tomando LIMIT 1).
#      - LATERAL permite que la subconsulta haga referencia a re.route_id
#        y al stop_id de la estación principal.
#      - LEFT JOIN asegura que aunque no haya pasos, la ruta aparezca
#        con p.vehicle_id = NULL.
#   5. WHERE e.stop_id = $1 : filtramos la estación.
#   6. ORDER BY r.nombre_corto, r.route_id : ordenamos las rutas
#      por nombre corto.
# 


# Funciones.

async def get_estaciones_de_ruta(
    conn: asyncpg.Connection,
    route_id: str,
) -> list[Estacion]:
    """
    Obtiene todas las estaciones de una ruta.

    Args:
        conn: Conexión activa a PostgreSQL (asyncpg).
        route_id: Identificador de la ruta.

    Returns:
        Lista de objetos Estacion, ordenados según su posición en la ruta.
        Si la ruta no existe o no tiene estaciones, retorna lista vacía.

    Example:
        >>> estaciones = await get_estaciones_de_ruta(conn, "19f29")
        >>> len(estaciones)
        20
    """
    filas = await conn.fetch(_SQL_ESTACIONES_DE_RUTA, route_id)
    return [Estacion(**dict(f)) for f in filas]


async def get_estacion_cercana(
    conn: asyncpg.Connection,
    lat: float,
    lon: float,
) -> Estacion | None:
    """
    Encuentra la estación más cercana a un punto geográfico usando el índice espacial.

    La consulta usa el operador `<->` (KNN) sobre la columna `ubicacion`, 
    que aprovecha el índice GIST para ser eficiente.

    Args:
        conn: Conexión activa a PostgreSQL.
        lat: Latitud del punto en grados decimales.
        lon: Longitud del punto en grados decimales.

    Returns:
        Objeto Estacion de la más cercana, o None si no hay estaciones.

    Example:
        >>> estacion = await get_estacion_cercana(conn, 19.4326, -99.1332)
        >>> print(estacion.nombre)
        'Zócalo'
    """
    fila = await conn.fetchrow(_SQL_ESTACION_CERCANA, lat, lon)
    if fila is None:
        return None
    return Estacion(**dict(fila))


async def get_estado_estacion(
    conn: asyncpg.Connection,
    stop_id: str,
) -> EstadoEstacion | None:
    """
    Obtiene el estado completo de una estación: su nombre y, para cada ruta
    que pasa por ella, el último paso registrado (si existe).

    La consulta usa un LATERAL JOIN para obtener el último paso de cada ruta
    en una sola consulta, evitando hacer una consulta separada por cada ruta.

    Args:
        conn: Conexión activa a PostgreSQL.
        stop_id: Identificador de la estación ("fa078a").

    Returns:
        Objeto EstadoEstacion con el nombre de la estación y la lista de rutas
        que pasan por ella, cada una con su último paso (si existe).
        Si la estación no existe, retorna None.

    Example:
        >>> estado = await get_estado_estacion(conn, "fa078a")
        >>> print(estado.nombre)
        'Insurgentes'
        >>> for ruta in estado.rutas:
        ...     print(ruta.nombre_corto, ruta.ultimo_paso.detectado_en if ruta.ultimo_paso else "sin datos")
    """
    filas = await conn.fetch(_SQL_ESTADO_ESTACION, stop_id)
    if not filas:
        return None

    nombre = filas[0]["nombre"]
    rutas = []

    for f in filas:
        # Si hay datos de paso, construir el resumen; de lo contrario None
        ultimo_paso = None
        if f["vehicle_id"] is not None:
            ultimo_paso = UltimoPasoResumen(
                vehicle_id=f["vehicle_id"],
                label=f["vehiculo_label"],
                detectado_en=f["detectado_en"],
            )

        # Añadir el color con # si existe
        color = f"#{f['color']}" if f["color"] else None

        rutas.append(RutaConUltimoPaso(
            route_id=f["route_id"],
            nombre_corto=f["nombre_corto"],
            nombre_largo=f["nombre_largo"],
            color=color,
            ultimo_paso=ultimo_paso,
        ))

    return EstadoEstacion(
        stop_id=stop_id,
        nombre=nombre,
        rutas=rutas,
    )