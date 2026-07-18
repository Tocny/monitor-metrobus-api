"""
Carga el GTFS estático de Metrobús en las tablas:
  - rutas
  - estaciones
  - ruta_estaciones
  - shapes

Se corre UNA SOLA VEZ, no en cada arranque del servicio.
Usa UPSERT (ON CONFLICT), así que correrlo de nuevo con un GTFS
actualizado refresca los datos sin duplicar filas.

Uso (dentro del contenedor):
    docker compose exec api python -m scripts.cargar_gtfs_estatico ruta/al/.zip

Advertencias:
    - El archivo ZIP debe contener los archivos estándar de GTFS:
      agency.txt, routes.txt, trips.txt, stop_times.txt, stops.txt, shapes.txt.
    - El script asume que shape_id = route_id.
"""

import asyncio
import csv
import io
import sys
import zipfile
from typing import Dict, List, Set, Tuple, Generator, Optional

import asyncpg

from app.core.config import get_settings
from app.db.schema import DDL_SQL

# Mapeo de direction_id del GTFS a texto legible
SENTIDOS: Dict[str, str] = {"0": "IDA", "1": "REGRESO"}


def leer_csv_de_zip(z: zipfile.ZipFile, nombre: str) -> Generator[Dict[str, str], None, None]:
    """
    Generador que lee un archivo CSV dentro de un ZIP y devuelve filas como diccionarios.

    Busca el archivo sin distinguir mayúsculas/minúsculas en el nombre,
    lo abre con codificación UTF-8 con BOM (utf-8-sig).

    Args:
        z: Objeto ZipFile abierto.
        nombre: Nombre del archivo a buscar (ej. "routes.txt").

    Yields:
        Diccionario con los datos de cada fila (claves = nombres de columnas).

    Raises:
        FileNotFoundError: Si el archivo no existe dentro del ZIP.

    Example:
        >>> with zipfile.ZipFile("gtfs.zip") as z:
        ...     for row in leer_csv_de_zip(z, "routes.txt"):
        ...         print(row["route_id"])
    """
    candidato = next((n for n in z.namelist() if n.lower().endswith(nombre)), None)
    if candidato is None:
        raise FileNotFoundError(f"No se encontró {nombre} dentro del zip GTFS.")
    with z.open(candidato) as f:
        texto = io.TextIOWrapper(f, encoding="utf-8-sig")
        yield from csv.DictReader(texto)


def detectar_agency_id_metrobus(z: zipfile.ZipFile) -> str:
    """
    Detecta el agency_id correspondiente a Metrobús en el archivo agency.txt.

    Estrategia:
        1. Si hay una sola agencia, se usa directamente.
        2. Si hay múltiples, busca la que tenga "metrobus" en el nombre.
        3. Si no encuentra ninguna, lanza una excepción con la lista de agencias.

    Args:
        z: Objeto ZipFile.

    Returns:
        El agency_id de Metrobús.

    Raises:
        RuntimeError: Si no se puede determinar el agency_id.
        FileNotFoundError: Si agency.txt no existe.

    Example:
        >>> with zipfile.ZipFile("gtfs.zip") as z:
        ...     agency_id = detectar_agency_id_metrobus(z)
        ...     print(agency_id)
        '1339'
    """
    agencias = list(leer_csv_de_zip(z, "agency.txt"))

    if len(agencias) == 1:
        agencia = agencias[0]
        print(
            f"Una sola agencia encontrada: id={agencia['agency_id']} "
            f"nombre='{agencia.get('agency_name', '')}'. Se usará directamente."
        )
        return agencia["agency_id"]

    for fila in agencias:
        if "metrobus" in fila.get("agency_name", "").lower():
            return fila["agency_id"]

    nombres = [(a["agency_id"], a.get("agency_name", "")) for a in agencias]
    raise RuntimeError(f"No se pudo detectar el agency_id de Metrobus. Agencias: {nombres}")


def extraer_datos_metrobus(zip_path: str) -> Tuple[Dict, Dict, List[Tuple]]:
    """
    Extrae rutas, estaciones y relaciones ruta-estación desde el GTFS estático.

    Procesa los archivos:
        - agency.txt (para filtrar por agencia)
        - routes.txt (obtiene rutas de Metrobús)
        - trips.txt (relaciona trips con rutas y sentido)
        - stop_times.txt (relaciona paradas con trips)
        - stops.txt (obtiene coordenadas de las paradas usadas)

    El resultado son tres estructuras para tres tablas:
        - rutas: {route_id: {nombre_corto, nombre_largo, color}}
        - estaciones: {stop_id: {nombre, lat, lon}}
        - ruta_estaciones: [(route_id, stop_id, sentido, orden), ...]

    Args:
        zip_path: Ruta al archivo ZIP del GTFS estático.

    Returns:
        Tupla con (rutas, estaciones, ruta_estaciones).

    Raises:
        FileNotFoundError: Si falta algún archivo importante dentro del ZIP.
        RuntimeError: Si no se puede detectar la agencia de Metrobús.

    Example:
        >>> rutas, estaciones, ruta_estaciones = extraer_datos_metrobus("gtfs.zip")
        >>> len(rutas)
        42
    """
    with zipfile.ZipFile(zip_path) as z:
        try:
            agency_id_mb = detectar_agency_id_metrobus(z)
            print(f"agency_id de Metrobus: {agency_id_mb}")
        except FileNotFoundError:
            agency_id_mb = None
            print("agency.txt no encontrado -- se asume que todo el archivo es de Metrobus.")

        # --- Rutas ---
        rutas: Dict[str, Dict] = {}
        for fila in leer_csv_de_zip(z, "routes.txt"):
            if agency_id_mb is None or fila.get("agency_id") == agency_id_mb:
                rutas[fila["route_id"]] = {
                    "nombre_corto": fila.get("route_short_name", ""),
                    "nombre_largo": fila.get("route_long_name", ""),
                    "color": fila.get("route_color", ""),
                }
        print(f"Rutas de Metrobús encontradas: {len(rutas)}")

        # --- Trips (viajes) ---
        trips: Dict[str, Tuple[str, str]] = {}
        for fila in leer_csv_de_zip(z, "trips.txt"):
            route_id = fila.get("route_id")
            if route_id in rutas:
                sentido = SENTIDOS.get(fila.get("direction_id", "0"), "IDA")
                trips[fila["trip_id"]] = (route_id, sentido)
        print(f"Viajes (trips) relevantes: {len(trips)}")

        # --- Stop Times (horarios de parada) ---
        orden_por_combo: Dict[Tuple[str, str, str], int] = {}
        stops_usados: Set[str] = set()
        for fila in leer_csv_de_zip(z, "stop_times.txt"):
            trip_id = fila.get("trip_id")
            if trip_id not in trips:
                continue
            route_id, sentido = trips[trip_id]
            stop_id = fila["stop_id"]
            secuencia = int(fila["stop_sequence"])
            combo = (route_id, stop_id, sentido)
            # Si ya existe, tomamos la secuencia más baja (primera aparición)
            if combo not in orden_por_combo or secuencia < orden_por_combo[combo]:
                orden_por_combo[combo] = secuencia
            stops_usados.add(stop_id)
        print(f"Combinaciones ruta-estación-sentido: {len(orden_por_combo)}")
        print(f"Estaciones distintas usadas: {len(stops_usados)}")

        # --- Paradas (estaciones) ---
        estaciones: Dict[str, Dict] = {}
        for fila in leer_csv_de_zip(z, "stops.txt"):
            if fila["stop_id"] in stops_usados:
                estaciones[fila["stop_id"]] = {
                    "nombre": fila.get("stop_name", ""),
                    "lat": float(fila["stop_lat"]),
                    "lon": float(fila["stop_lon"]),
                }

        # --- Relaciones ruta-estación ---
        ruta_estaciones = [
            (route_id, stop_id, sentido, orden)
            for (route_id, stop_id, sentido), orden in orden_por_combo.items()
        ]

        return rutas, estaciones, ruta_estaciones


def extraer_shapes(zip_path: str, route_ids: Set[str]) -> List[Tuple[str, int, float, float]]:
    """
    Extrae los puntos de geometría (shapes) para las rutas cargadas.

    Lee el archivo shapes.txt y filtra solo los puntos cuyo shape_id
    coincide con un route_id válido (shape_id = route_id).

    Args:
        zip_path: Ruta al archivo ZIP del GTFS estático.
        route_ids: Conjunto de route_ids válidos (los que se van a cargar).

    Returns:
        Lista de tuplas: (route_id, secuencia, lat, lon).

    Example:
        >>> shapes = extraer_shapes("gtfs.zip", {"19429", "19430"})
        >>> len(shapes)
        1245
    """
    puntos: List[Tuple[str, int, float, float]] = []
    with zipfile.ZipFile(zip_path) as z:
        for fila in leer_csv_de_zip(z, "shapes.txt"):
            shape_id = fila["shape_id"]
            if shape_id not in route_ids:
                continue
            puntos.append((
                shape_id,
                int(fila["shape_pt_sequence"]),
                float(fila["shape_pt_lat"]),
                float(fila["shape_pt_lon"]),
            ))
    print(f"Puntos de shapes encontrados: {len(puntos)}")
    return puntos


async def cargar_en_base_de_datos(
    zip_path: str,
    rutas: Dict,
    estaciones: Dict,
    ruta_estaciones: List[Tuple],
) -> None:
    """
    Carga los datos extraídos en la base de datos.

    Si los registros ya existen, los actualiza; si no, los inserta. 
    Esto permite ejecutar el script n veces sin duplicar datos (viva UPSERT)

    orden de carga:
        1. Rutas (para llaves foraneas para estaciones.ruta_id )
        2. Estaciones (para llaves foranes de estaciones.stop_id)
        3. Ruta-Estaciones (depende de las dos anteriores)
        4. Shapes (depende de rutas)

    Args:
        zip_path: Ruta al archivo ZIP.
        rutas: Diccionario de rutas {route_id: {nombre_corto, nombre largo ...}}.
        estaciones: Diccionario de estaciones {stop_id: {nombre, lat, lon}}.
        ruta_estaciones: Lista de tuplas (route_id, stop_id, sentido, orden).

    Raises:
        asyncpg.exceptions.PostgresError: Si falla alguna operación en BD.

    Example:
        >>> await cargar_en_base_de_datos("gtfs.zip", rutas, estaciones, ruta_estaciones)
        Rutas insertadas/actualizadas: 42
        Estaciones insertadas/actualizadas: 156
    """
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    try:
        # Asegurar que el esquema existe
        await conn.execute(DDL_SQL)

        # --- Rutas (UPSERT) ---
        if rutas:
            await conn.executemany(
                """
                INSERT INTO rutas (route_id, nombre_corto, nombre_largo, color, agencia)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (route_id) DO UPDATE SET
                    nombre_corto = EXCLUDED.nombre_corto,
                    nombre_largo = EXCLUDED.nombre_largo,
                    color = EXCLUDED.color
                """,
                [
                    (rid, d["nombre_corto"], d["nombre_largo"], d["color"], "Metrobus")
                    for rid, d in rutas.items()
                ],
            )
            print(f"Rutas insertadas/actualizadas: {len(rutas)}")

        # --- Estaciones (UPSERT) ---
        if estaciones:
            await conn.executemany(
                """
                INSERT INTO estaciones (stop_id, nombre, lat, lon, ubicacion)
                VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($4, $3), 4326)::geography)
                ON CONFLICT (stop_id) DO UPDATE SET
                    nombre    = EXCLUDED.nombre,
                    lat       = EXCLUDED.lat,
                    lon       = EXCLUDED.lon,
                    ubicacion = EXCLUDED.ubicacion
                """,
                [(sid, d["nombre"], d["lat"], d["lon"]) for sid, d in estaciones.items()],
            )
            print(f"Estaciones insertadas/actualizadas: {len(estaciones)}")

        # --- Ruta-Estaciones (UPSERT) ---
        if ruta_estaciones:
            await conn.executemany(
                """
                INSERT INTO ruta_estaciones (route_id, stop_id, sentido, orden)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (route_id, stop_id, sentido) DO UPDATE SET
                    orden = EXCLUDED.orden
                """,
                ruta_estaciones,
            )
            print(f"Relaciones ruta-estación insertadas/actualizadas: {len(ruta_estaciones)}")

        # --- Shapes (UPSERT) ---
        shapes = extraer_shapes(zip_path, set(rutas.keys()))
        if shapes:
            await conn.executemany(
                """
                INSERT INTO shapes (route_id, secuencia, lat, lon)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (route_id, secuencia) DO UPDATE SET
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon
                """,
                shapes,
            )
            print(f"Puntos de shapes insertados/actualizados: {len(shapes)}")

    finally:
        await conn.close()


async def main_async() -> None:
    """
    Función main asncrona (para usar await) que ejecuta la extracción y carga de datos.

    Lee el argumento de la línea de comandos (que debe ser la ruta al ZIP), extrae los
    datos y los carga BD.

    Raises:
        SystemExit: Si no se proporciona el argumento requerido.
    """
    if len(sys.argv) != 2:
        print("Uso: python -m scripts.cargar_gtfs_estatico /ruta/al/gtfs_metrobus.zip")
        sys.exit(1)

    zip_path = sys.argv[1]
    print(f"Procesando {zip_path} ...")
    rutas, estaciones, ruta_estaciones = extraer_datos_metrobus(zip_path)
    await cargar_en_base_de_datos(zip_path, rutas, estaciones, ruta_estaciones)
    print("Listo.")


def main() -> None:
    """Main sincrono que ejecuta la función main asincrona."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()