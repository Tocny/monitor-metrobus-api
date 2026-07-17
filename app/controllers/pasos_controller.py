"""
Controller: pasos registrados.
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_db
from app.services.pasos_service import obtener_ultimo_paso, obtener_ultimos_pasos

router = APIRouter(prefix="/estaciones", tags=["pasos"])


@router.get("/{stop_id}/ultimo-paso")
async def ultimo_paso(
    stop_id: str,
    route_id: str = Query(..., description="ID de la ruta a consultar"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve el ultimo paso confirmado de un camion de la ruta
    indicada en esta estacion.
    """
    paso = await obtener_ultimo_paso(conn, stop_id, route_id)
    if paso is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sin pasos registrados para la estacion {stop_id} en la ruta {route_id}.",
        )
    return paso.model_dump()


@router.get("/{stop_id}/pasos")
async def historial_pasos(
    stop_id: str,
    route_id: str = Query(..., description="ID de la ruta a consultar"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve los ultimos pasos registrados (hasta 10) de la ruta
    indicada en esta estacion.
    """
    pasos = await obtener_ultimos_pasos(conn, stop_id, route_id)
    return [p.model_dump() for p in pasos]