"""
Controller: datos geograficos para el mapa (Mapbox GL JS).

Todos los endpoints devuelven GeoJSON estandar (RFC 7946).

GET /mapa/estaciones  → FeatureCollection de puntos (estaciones)
GET /mapa/vehiculos   → FeatureCollection de puntos (posiciones actuales)
GET /mapa/rutas       → FeatureCollection de LineStrings (trazos de linea)
"""

import asyncpg
from fastapi import APIRouter, Depends

from app.db.session import get_db
from app.services.mapa_service import (
    obtener_estaciones_para_mapa,
    obtener_rutas_para_mapa,
    obtener_vehiculos_para_mapa,
)

router = APIRouter(prefix="/mapa", tags=["mapa"])


@router.get("/estaciones")
async def mapa_estaciones(conn: asyncpg.Connection = Depends(get_db)):
    """Todas las estaciones de Metrobus como GeoJSON FeatureCollection."""
    estaciones = await obtener_estaciones_para_mapa(conn)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [e.lon, e.lat],
            },
            "properties": {
                "stop_id": e.stop_id,
                "nombre": e.nombre,
            },
        }
        for e in estaciones
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/vehiculos")
async def mapa_vehiculos(conn: asyncpg.Connection = Depends(get_db)):
    """
    Posiciones actuales de todos los vehiculos activos como GeoJSON
    FeatureCollection. Refresca cada 30s en el cliente para el mapa
    en vivo.
    """
    vehiculos = await obtener_vehiculos_para_mapa(conn)
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
    de LineStrings.
    """
    rutas, shapes = await obtener_rutas_para_mapa(conn)
    rutas_dict = {r.route_id: r for r in rutas}

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[p.lon, p.lat] for p in puntos],
            },
            "properties": {
                "route_id": route_id,
                "nombre_corto": rutas_dict[route_id].nombre_corto if route_id in rutas_dict else None,
                "nombre_largo": rutas_dict[route_id].nombre_largo if route_id in rutas_dict else None,
                "color": f"#{rutas_dict[route_id].color}" if route_id in rutas_dict and rutas_dict[route_id].color else "#000000",
            },
        }
        for route_id, puntos in shapes.items()
    ]
    return {"type": "FeatureCollection", "features": features}