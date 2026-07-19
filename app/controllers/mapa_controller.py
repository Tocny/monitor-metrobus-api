"""
Controller: datos geográficos para el mapa.

Proporciona endpoints que devuelven datos geoespaciales en formato GeoJSON

Permite obtener:
    - todas las estaciones como puntos.
    - la posición actual de todos los vehículos como puntos.
    - los trazados de todas las rutas como líneas.

Dependencias:
    - FastAPI
    - asyncpg 
    - app.services.mapa_service
"""

import asyncpg
from fastapi import APIRouter, Depends

from app.db.session import get_db
from app.services.mapa_service import (
    obtener_estaciones_para_mapa,
    obtener_rutas_para_mapa,
    obtener_vehiculos_para_mapa,
)

# Router con prefijo "/mapa"
router = APIRouter(prefix="/mapa", tags=["mapa"])


@router.get("/estaciones")
async def mapa_estaciones(conn: asyncpg.Connection = Depends(get_db)):
    """
    Obtiene todas las estaciones de Metrobús como un 
    GeoJSON FeatureCollection de puntos.

    Cada feature representa una estación con su geometría (Point) y
    propiedades. Los puntos se pueden dibujar en el mapa.

    Args:
        conn: Conexión a la base de datos.

    Example:
        GET /mapa/estaciones
        Response:
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-99.140939, 19.467312]
                    },
                    "properties": {
                        "stop_id": "fa077f",
                        "nombre": "Potrero"
                    }
                },
                ...
            ]
        }
    """
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
    Obtiene la posición actual de todos los vehículos activos como un
    GeoJSON FeatureCollection de puntos.

    Este endpoint se actualiza cada 30 segundos (frecuencia del worker
    de polling).

    Cada feature representa un vehículo con su geometría y propiedades relevantes.

    Args:
        conn: Conexión a la base de datos.

    Example:
        GET /mapa/vehiculos
        Response:
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-99.140939, 19.467312]
                    },
                    "properties": {
                        "vehicle_id": "69379",
                        "label": "1203",
                        "route_id": "19429",
                        "velocidad": 12.5,
                        "estacion_actual_id": "fa077f"
                    }
                },
                ...
            ]
        }
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
    Obtiene los trazados geométricos de todas las rutas como un GeoJSON
    FeatureCollection de LineStrings.

    Cada feature representa una ruta completa con su geometría y propiedades.
    Los puntos de cada ruta se obtienen de la tabla shapes y se ordenan 
    para formar la línea continua.

    Args:
        conn: Conexión a la base de datos.

    Example:
        GET /mapa/rutas
        Response:
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-99.140939, 19.467312],
                            [-99.140775, 19.467537],
                            ...
                        ]
                    },
                    "properties": {
                        "route_id": "19429",
                        "nombre_corto": "3",
                        "nombre_largo": "L03d03-1 tenayuca - la raza",
                        "color": "#7A9A01"
                    }
                },
                ...
            ]
        }
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