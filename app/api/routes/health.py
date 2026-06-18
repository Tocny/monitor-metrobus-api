"""
Endpoints de verificacion de salud del servicio.

Sirve para confirmar, desde Fase 0, que: la app levanta, lee bien
la configuracion desde variables de entorno, y puede conectarse a
la base de datos PostgreSQL/PostGIS del docker-compose.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    settings = get_settings()
    db_ok = await check_db_connection()

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.environment,
        "database_connected": db_ok,
    }
