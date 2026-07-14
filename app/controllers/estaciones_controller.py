"""
Controller: estaciones.
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_db
from app.repositories.estaciones_repository import (
    get_estacion_cercana,
    get_estado_estacion,
)

router = APIRouter(prefix="/estaciones", tags=["estaciones"])


@router.get("/cercana")
async def estacion_cercana(
    lat: float = Query(..., description="Latitud del usuario"),
    lon: float = Query(..., description="Longitud del usuario"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve la estacion de Metrobus mas cercana a las coordenadas
    indicadas.
    """
    estacion = await get_estacion_cercana(conn, lat, lon)
    if estacion is None:
        raise HTTPException(status_code=404, detail="No se encontraron estaciones.")
    return estacion.model_dump()


@router.get("/{stop_id}/estado")
async def estado_estacion(
    stop_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Dada una estacion, devuelve todas las rutas que pasan por ella
    y el ultimo paso registrado de cada una. Es el endpoint principal
    para responder: 'ya paso el camion?' y 'hace cuanto?'
    """
    estado = await get_estado_estacion(conn, stop_id)
    if estado is None:
        raise HTTPException(
            status_code=404,
            detail=f"Estacion '{stop_id}' no encontrada.",
        )
    return estado.model_dump()