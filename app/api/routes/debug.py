"""
Controller: endpoints de depuración.

Proporciona endpoints diseñados para validar que la
integración con el feed GTFS-RT del Metrobús funciona correctamente, 
desde la autenticación con SONDA hasta la
decodificación de los datos en tiempo real.

Estos endpoints son útiles durante el desarrollo y las pruebas,
"""

from fastapi import APIRouter, HTTPException

from app.services.metrobus_client import (
    ErrorAutenticacionMetrobus,
    obtener_vehiculos_actuales,
)

# Router para endpoints de depuración, prefijo "/debug"
router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/feed")
async def debug_feed():
    """
    Endpoint de diagnóstico para validar la conexión con el feed GTFS-RT.

    Realiza las siguientes operaciones:
        1. Autentica contra el endpoint partnerValidation de SONDA.
        2. Descarga el feed binario desde la URL.
        3. Decodifica el feed.
        4. Devuelve un resumen con el número total de vehículos y
           los primeros 5 vehículos.

    Es útil para confirmar que:
        - Las credenciales son correctas.
        - El endpoint de autenticación responde correctamente.
        - Las URLs prefirmadas se generan y son accesibles.
        - El feed se descarga y decodifica sin errores.

    Returns:
        Diccionario con:
            - total_vehiculos: Número total de vehículos en el feed.
            - muestra: Lista de los primeros 5 vehículos.

    Raises:
        HTTPException 502: Si ocurre un error de autenticación con el
            proveedor (ErrorAutenticacionMetrobus), se devuelve un
            error 502 (Bad Gateway) con el detalle del error.
        HTTPException 500: Para otros errores inesperados.

    Example:
        GET /debug/feed
        Response:
        {
            "total_vehiculos": 829,
            "muestra": [
                {"vehicle_id": "69379", "label": "1203", ...},
                ...
            ]
        }
    """
    try:
        vehiculos = await obtener_vehiculos_actuales()
    except ErrorAutenticacionMetrobus as e:
        # El error de autenticación se transforma en un 502 porque es un
        # problema con el proveedor externo, no con nuestra app.
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Devuelve un resumen con la cantidad total y una muestra de 5 vehículos
    return {
        "total_vehiculos": len(vehiculos),
        "muestra": [v.model_dump() for v in vehiculos[:5]],
    }