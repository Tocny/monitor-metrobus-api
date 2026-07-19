"""
Endpoints de verificación de salud del servicio.

Proporciona un endpoint estándar de health check (/health) que permite
verificar que la aplicación está funcionando correctamente, que la
configuración se carga desde variables de entorno, y que la conexión
a la base de datos está activa.

"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_db_connection

# Router para endpoints de salud
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Endpoint de verificación de salud del servicio.

    Realiza las siguientes comprobaciones:
        1. Carga la configuración desde variables de entorno (con Settings).
        2. Intenta establecer una conexión con la base de datos PostgreSQL
           (ejecuta "SELECT 1" para verificar que responde).
        3. Devuelve un resumen del estado.

    El estado puede ser:
        - "ok": La base de datos responde correctamente.
        - "degraded": La aplicación está funcionando pero la base de datos
          no responde.

    Returns:
        Diccionario con los siguientes campos:
            - status: "ok" si la base de datos responde, "degraded" si no.
            - app: Nombre de la aplicación.
            - environment: Entorno de ejecución.
            - database_connected: Booleano que indica si la BD responde.

    Example:
        GET /health
        Response:
        {
            "status": "ok",
            "app": "Monitor Metrobus API",
            "environment": "development",
            "database_connected": true
        }

        Si la base de datos está caída:
        {
            "status": "degraded",
            "app": "Monitor Metrobus API",
            "environment": "development",
            "database_connected": false
        }
    """
    settings = get_settings()
    db_ok = await check_db_connection()

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.environment,
        "database_connected": db_ok,
    }