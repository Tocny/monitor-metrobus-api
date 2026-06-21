"""
Carga el GTFS estatico de Metrobus en las tablas rutas / estaciones /
ruta_estaciones, via asyncpg directo (sin ORM).

Se corre UNA SOLA VEZ (o cuando Metrobus publique una version nueva
del GTFS) -- no en cada arranque del servicio. Es idempotente: usa
UPSERT (ON CONFLICT), asi que correrlo de nuevo con un GTFS
actualizado simplemente refresca los datos sin duplicar filas.

Uso (dentro del contenedor):
    python -m scripts.cargar_gtfs_estatico /ruta/al/gtfs_metrobus.zip
"""

import asyncio
import csv
import io
import sys
import zipfile

import asyncpg

from app.core.config import get_settings
from app.db.schema import DDL_SQL

SENTIDOS = {"0": "IDA", "1": "REGRESO"}


def leer_csv_de_zip(z: zipfile.ZipFile, nombre: str):
    """Generador que entrega filas (dict) de un archivo dentro del zip GTFS."""
    candidato = next((n for n in z.namelist() if n.lower().endswith(nombre)), None)
    if candidato is None:
        raise FileNotFoundError(f"No se encontro {nombre} dentro del zip GTFS.")
    with z.open(candidato) as f:
        texto = io.TextIOWrapper(f, encoding="utf-8-sig")
        yield from csv.DictReader(texto)


def detectar_agency_id_metrobus(z: zipfile.ZipFile) -> str:
    """
    Si hay una sola agencia en agency.txt (caso tipico de un GTFS
    especifico de Metrobus), se usa directamente. Si hay varias
    (GTFS combinado de toda la ciudad), se busca por nombre.
    """
    agencias = list(leer_csv_de_zip(z, "agency.txt"))

    if len(agencias) == 1:
        agencia = agencias[0]
        print(
            f"Una sola agencia encontrada: id={agencia['agency_id']} "
            f"nombre='{agencia.get('agency_name', '')}'. Se usara directamente."
        )
        return agencia["agency_id"]

    for fila in agencias:
        if "metrobus" in fila.get("agency_name", "").lower():
            return fila["agency_id"]

    nombres = [(a["agency_id"], a.get("agency_name", "")) for a in agencias]
    raise RuntimeError(f"No se pudo detectar el agency_id de Metrobus. Agencias: {nombres}")


def extraer_datos_metrobus(zip_path: str):
    """Procesa el GTFS estatico en streaming y devuelve rutas, estaciones y ruta_estaciones."""
    with zipfile.ZipFile(zip_path) as z:
        try:
            agency_id_mb = detectar_agency_id_metrobus(z)
            print(f"agency_id de Metrobus: {agency_id_mb}")
        except FileNotFoundError:
            agency_id_mb = None
            print("agency.txt no encontrado -- se asume que todo el archivo es de Metrobus.")

        rutas = {}
        for fila in leer_csv_de_zip(z, "routes.txt"):
            if agency_id_mb is None or fila.get("agency_id") == agency_id_mb:
                rutas[fila["route_id"]] = {
                    "nombre_corto": fila.get("route_short_name", ""),
                    "nombre_largo": fila.get("route_long_name", ""),
                    "color": fila.get("route_color", ""),
                }
        print(f"Rutas de Metrobus encontradas: {len(rutas)}")

        trips: dict[str, tuple[str, str]] = {}
        for fila in leer_csv_de_zip(z, "trips.txt"):
            route_id = fila.get("route_id")
            if route_id in rutas:
                sentido = SENTIDOS.get(fila.get("direction_id", "0"), "IDA")
                trips[fila["trip_id"]] = (route_id, sentido)
        print(f"Viajes (trips) relevantes: {len(trips)}")

        orden_por_combo: dict[tuple[str, str, str], int] = {}
        stops_usados: set[str] = set()
        for fila in leer_csv_de_zip(z, "stop_times.txt"):
            trip_id = fila.get("trip_id")
            if trip_id not in trips:
                continue
            route_id, sentido = trips[trip_id]
            stop_id = fila["stop_id"]
            secuencia = int(fila["stop_sequence"])
            combo = (route_id, stop_id, sentido)
            if combo not in orden_por_combo or secuencia < orden_por_combo[combo]:
                orden_por_combo[combo] = secuencia
            stops_usados.add(stop_id)
        print(f"Combinaciones ruta-estacion-sentido: {len(orden_por_combo)}")
        print(f"Estaciones distintas usadas: {len(stops_usados)}")

        estaciones = {}
        for fila in leer_csv_de_zip(z, "stops.txt"):
            if fila["stop_id"] in stops_usados:
                estaciones[fila["stop_id"]] = {
                    "nombre": fila.get("stop_name", ""),
                    "lat": float(fila["stop_lat"]),
                    "lon": float(fila["stop_lon"]),
                }

        ruta_estaciones = [
            (route_id, stop_id, sentido, orden)
            for (route_id, stop_id, sentido), orden in orden_por_combo.items()
        ]

        return rutas, estaciones, ruta_estaciones


async def cargar_en_base_de_datos(rutas, estaciones, ruta_estaciones):
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    try:
        # Asegura que las tablas/extension existan (por si se corre
        # este script antes de haber levantado la app una vez).
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
                    nombre = EXCLUDED.nombre,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
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
            print(f"Relaciones ruta-estacion insertadas/actualizadas: {len(ruta_estaciones)}")
    finally:
        await conn.close()


async def main_async():
    if len(sys.argv) != 2:
        print("Uso: python -m scripts.cargar_gtfs_estatico /ruta/al/gtfs_metrobus.zip")
        sys.exit(1)

    zip_path = sys.argv[1]
    print(f"Procesando {zip_path} ...")
    rutas, estaciones, ruta_estaciones = extraer_datos_metrobus(zip_path)
    await cargar_en_base_de_datos(rutas, estaciones, ruta_estaciones)
    print("Listo.")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
