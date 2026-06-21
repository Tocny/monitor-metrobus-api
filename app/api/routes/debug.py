"""
Endpoints TEMPORALES de depuracion -- pensados solo para validar, a
mano, que el login y la descarga del feed funcionan de extremo a
extremo. Quitar este router (o protegerlo) antes de exponer el
servicio publicamente: revela conteos y muestras del feed sin
autenticacion de tu lado.
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
    Hace login (o reusa el token cacheado), descarga el feed,
    lo decodifica, y devuelve un resumen + una muestra de 5 vehiculos.
    Util para confirmar que METROBUS_TOKEN_FIELD y el mecanismo de
    autenticacion en .env estan configurados correctamente.
    """
    try:
        vehiculos = await obtener_vehiculos_actuales()
    except ErrorAutenticacionMetrobus as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {
        "total_vehiculos": len(vehiculos),
        "muestra": vehiculos[:5],
    }
