"""
Controller: pasos registrados.

GET /estaciones/{stop_id}/ultimo-paso?route_id=
    Responde: "ya paso el camion de la linea X?" y "hace cuanto?"

GET /estaciones/{stop_id}/pasos?route_id=
    Devuelve el historial reciente (hasta 10) de pasos en esa
    estacion para esa ruta.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.db.session import get_db
from app.repositories.pasos_repository import get_ultimo_paso, get_ultimos_pasos

router = APIRouter(prefix="/estaciones", tags=["pasos"])


@router.get("/{stop_id}/ultimo-paso")
async def ultimo_paso(
    stop_id: str,
    route_id: str = Query(..., description="ID de la ruta a consultar"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve el ultimo paso confirmado de un camion de la ruta
    indicada en esta estacion, con el timestamp exacto.
    """
    paso = await get_ultimo_paso(conn, stop_id, route_id)
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
    indicada en esta estacion. Util para estimar frecuencia de paso.
    """
    pasos = await get_ultimos_pasos(conn, stop_id, route_id)
    return [p.model_dump() for p in pasos]