"""
Controller: estaciones.

GET /estaciones/cercana?lat=&lon=
    Devuelve la estacion mas cercana al usuario usando el indice
    GIST de PostGIS.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.db.session import get_db
from app.repositories.estaciones_repository import get_estacion_cercana

router = APIRouter(prefix="/estaciones", tags=["estaciones"])


@router.get("/cercana")
async def estacion_cercana(
    lat: float = Query(..., description="Latitud del usuario"),
    lon: float = Query(..., description="Longitud del usuario"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve la estacion de Metrobus mas cercana a las coordenadas
    indicadas, con la distancia en metros.
    """
    estacion = await get_estacion_cercana(conn, lat, lon)
    if estacion is None:
        raise HTTPException(status_code=404, detail="No se encontraron estaciones.")
    return estacion.model_dump()