"""
Controller: Pasos registrados.

Proporciona endpoints para consultar el historial de pasos de vehículos
por estación y ruta.

Se puede procesar la información como:
    - "Ruta 1, pasó hace 2 minutos".
    - Historial de pasos de una ruta en una estación.

Los datos provienen de la tabla pasos_registrados, que es alimentada
por el worker de polling cada 30 segundos.

Dependencias:
    - FastAPI
    - asyncpg 
    - app.services.pasos_service
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_db
from app.services.pasos_service import obtener_ultimo_paso, obtener_ultimos_pasos

# Router con prefijo "/estaciones" (los endpoints operan sobre estaciones)
router = APIRouter(prefix="/estaciones", tags=["pasos"])


@router.get("/{stop_id}/ultimo-paso")
async def ultimo_paso(
    stop_id: str,
    route_id: str = Query(..., description="ID de la ruta a consultar (ej. '19429')"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve el último paso confirmado de un vehículo de la ruta
    indicada en esta estación.

    Args:
        stop_id: Identificador de la estación.
        route_id: Identificador de la ruta.
        conn: Conexión a la base de datos.

    Returns:
        Diccionario con los datos del último paso:
            - id: Identificador del registro.
            - estacion_id: stop_id de la estación.
            - route_id: route_id de la ruta.
            - vehicle_id: Identificador del vehículo.
            - label: Número visible del autobús.
            - detectado_en: Timestamp del paso.

    Raises:
        HTTPException 404: Si no hay pasos registrados.

    Example:
        GET /estaciones/fa078a/ultimo-paso?route_id=19429
        Response:
        {
            "id": 12345,
            "estacion_id": "fa078a",
            "route_id": "19429",
            "vehicle_id": "69379",
            "label": "1203",
            "detectado_en": "2026-07-18T14:23:45Z"
        }
    """
    paso = await obtener_ultimo_paso(conn, stop_id, route_id)
    if paso is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sin pasos registrados para la estación {stop_id} en la ruta {route_id}.",
        )
    return paso.model_dump()


@router.get("/{stop_id}/pasos")
async def historial_pasos(
    stop_id: str,
    route_id: str = Query(..., description="ID de la ruta a consultar (ej. '19429')"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve los últimos pasos registrados (max 10) de
    la ruta indicada en esta estación.

    Este endpoint es para mostrar un historial reciente.

    El número máximo de pasos retornados está definido por la constante
    MAX_PASOS_POR_ESTACION_RUTA en el repositorio de pasos (10).

    Args:
        stop_id: Identificador de la estación.
        route_id: Identificador de la ruta.
        conn: Conexión a la base de datos.

    Returns:
        Lista de diccionarios, cada uno con los datos de un paso:
            - id: Identificador del registro.
            - estacion_id: stop_id de la estación.
            - route_id: route_id de la ruta.
            - vehicle_id: Identificador del vehículo.
            - label: Número visible del autobús.
            - detectado_en: Timestamp del paso.

    Raises:
        HTTPException 404: Si no hay pasos registrados.

    Example:
        GET /estaciones/fa078a/pasos?route_id=19429
        Response:
        [
            {
                "id": 12345,
                "estacion_id": "fa078a",
                "route_id": "19429",
                "vehicle_id": "69379",
                "label": "1203",
                "detectado_en": "2026-07-18T14:23:45Z"
            },
            {
                "id": 12344,
                "estacion_id": "fa078a",
                "route_id": "19429",
                "vehicle_id": "69378",
                "label": "1202",
                "detectado_en": "2026-07-18T14:20:12Z"
            },
            ...
        ]
    """
    pasos = await obtener_ultimos_pasos(conn, stop_id, route_id)
    return [p.model_dump() for p in pasos]