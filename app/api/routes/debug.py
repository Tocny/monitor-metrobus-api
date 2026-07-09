"""
Controller: endpoints temporales de depuracion.

Pensados solo para validar que el feed funciona de extremo a extremo.
Quitar o proteger antes de exponer el servicio publicamente.
"""

from fastapi import APIRouter, HTTPException

from app.services.metrobus_client import (
    ErrorAutenticacionMetrobus,
    obtener_vehiculos_actuales,
)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/feed")
async def debug_feed():
    """
    Valida contra partnerValidation (o reusa las URLs cacheadas),
    descarga el feed, lo decodifica y devuelve un resumen + muestra
    de 5 vehiculos. Util para confirmar que las credenciales en .env
    son correctas y el feed responde.
    """
    try:
        vehiculos = await obtener_vehiculos_actuales()
    except ErrorAutenticacionMetrobus as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {
        "total_vehiculos": len(vehiculos),
        "muestra": [v.model_dump() for v in vehiculos[:5]],
    }