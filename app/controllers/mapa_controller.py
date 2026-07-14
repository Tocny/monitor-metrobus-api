"""
Controller: datos geograficos para el mapa (Mapbox GL JS).

Todos los endpoints devuelven GeoJSON estandar (RFC 7946).

GET /mapa/estaciones  → FeatureCollection de puntos (estaciones)
GET /mapa/vehiculos   → FeatureCollection de puntos (posiciones actuales)
GET /mapa/rutas       → FeatureCollection de LineStrings (trazos de linea)
"""

from fastapi import APIRouter, Depends
import asyncpg

from app.db.session import get_db
from app.repositories.estaciones_repository import get_estacion_cercana
from app.repositories.rutas_repository import get_todas_las_rutas
from app.repositories.shapes_repository import get_todos_los_puntos
from app.repositories.vehiculos_repository import get_todos_vehiculos

# Importamos get_db para estaciones -- necesitamos una query de "todas"
from app.db.session import get_db

router = APIRouter(prefix="/mapa", tags=["mapa"])

_SQL_TODAS_ESTACIONES = """
    SELECT stop_id, nombre, lat, lon FROM estaciones
"""


@router.get("/estaciones")
async def mapa_estaciones(conn: asyncpg.Connection = Depends(get_db)):
    """
    Todas las estaciones de Metrobus como GeoJSON FeatureCollection.
    """
    filas = await conn.fetch(_SQL_TODAS_ESTACIONES)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                # GeoJSON usa [lon, lat] -- no [lat, lon]
                "coordinates": [float(f["lon"]), float(f["lat"])],
            },
            "properties": {
                "stop_id": f["stop_id"],
                "nombre": f["nombre"],
            },
        }
        for f in filas
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/vehiculos")
async def mapa_vehiculos(conn: asyncpg.Connection = Depends(get_db)):
    """
    Posiciones actuales de todos los vehiculos activos como GeoJSON
    FeatureCollection. Refresca cada 30s en el cliente para el mapa
    en vivo.
    """
    vehiculos = await get_todos_vehiculos(conn)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [v.lon, v.lat],
            },
            "properties": {
                "vehicle_id": v.vehicle_id,
                "label": v.label,
                "route_id": v.route_id,
                "velocidad": v.velocidad,
                "estacion_actual_id": v.estacion_actual_id,
            },
        }
        for v in vehiculos
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/rutas")
async def mapa_rutas(conn: asyncpg.Connection = Depends(get_db)):
    """
    Trazos geometricos de todas las rutas como GeoJSON FeatureCollection
    de LineStrings. Incluye color y nombre comercial de cada linea para
    que Mapbox pueda estilizarlas correctamente.
    """
    rutas = {r.route_id: r for r in await get_todas_las_rutas(conn)}
    shapes = await get_todos_los_puntos(conn)

    features = []
    for route_id, puntos in shapes.items():
        ruta = rutas.get(route_id)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p.lon, p.lat] for p in puntos],
                },
                "properties": {
                    "route_id": route_id,
                    "nombre_corto": ruta.nombre_corto if ruta else None,
                    "nombre_largo": ruta.nombre_largo if ruta else None,
                    "color": f"#{ruta.color}" if ruta and ruta.color else "#000000",
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}