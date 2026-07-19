"""
Controller: Estaciones.

Proporciona endpoints para consultar información sobre estaciones del
Metrobús, incluyendo búsqueda por proximidad geográfica y estado
completo de una estación.

Estos endpoints son la interfaz pública para que en frontend se pueda
mostrar estaciones en el mapa y consultar su estado en tiempo real.

Dependencias:
    - FastAPI 
    - asyncpg 
    - app.services.estaciones_service 
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_db
from app.services.estaciones_service import (
    obtener_estacion_cercana,
    obtener_estado_estacion,
)

# Router con prefijo "/estaciones"
router = APIRouter(prefix="/estaciones", tags=["estaciones"])


@router.get("/cercana")
async def estacion_cercana(
    lat: float = Query(..., description="Latitud del usuario en grados decimales "),
    lon: float = Query(..., description="Longitud del usuario en grados decimales "),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Devuelve la estación de Metrobús más cercana a las coordenadas indicadas.

    Utiliza el índice gist para encontrar la estación
    más cercana (consulta KNN).

    Args:
        lat: Latitud del punto de referencia.
        lon: Longitud del punto de referencia.
        conn: Conexión a la base de datos.

    Returns:
        Diccionario con los datos de la estación más cercana:
            stop_id, nombre, lat, lon.

    Raises:
        HTTPException 404: Si no hay estaciones en la base de datos.
        HTTPException 500: Para errores inesperados.

    Example:
        GET /estaciones/cercana?lat=19.4326&lon=-99.1332
        Response:
        {
            "stop_id": "fa078a",
            "nombre": "Insurgentes",
            "lat": 19.423,
            "lon": -99.165
        }
    """
    estacion = await obtener_estacion_cercana(conn, lat, lon)
    if estacion is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron estaciones cercanas."
        )
    return estacion.model_dump()


@router.get("/{stop_id}/estado")
async def estado_estacion(
    stop_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Obtiene el estado completo de una estación.

    Devuelve el nombre de la estación y, para cada ruta que pasa por ella,
    el último paso registrado (vehículo, etiqueta y timestamp). La consulta
    se realiza en una sola operación.

    Este endpoint es clave para la vista de detalle de una estación.
    
    Args:
        stop_id: Identificador de la estación.
        conn: Conexión a la base de datos.

    Returns:
        Diccionario con el estado completo de la estación.

    Raises:
        HTTPException 404: Si el stop_id no existe en la base de datos.
        HTTPException 500: Para errores inesperados.

    Example:
        GET /estaciones/fa078a/estado
        Response:
        {
            "stop_id": "fa078a",
            "nombre": "Insurgentes",
            "rutas": [
                {
                    "route_id": "19429",
                    "nombre_corto": "3",
                    "color": "#7A9A01",
                    "ultimo_paso": {
                        "vehicle_id": "69379",
                        "label": "1203",
                        "detectado_en": "2026-07-18T14:23:45Z"
                    }
                },
                ...
            ]
        }
    """
    estado = await obtener_estado_estacion(conn, stop_id)
    if estado is None:
        raise HTTPException(
            status_code=404,
            detail=f"Estación '{stop_id}' no encontrada.",
        )
    return estado.model_dump()