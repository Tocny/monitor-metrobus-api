"""
Punto de entrada de la aplicacion.

En esta fase solo se registra el router de health-check. Las rutas de
negocio (estacion mas cercana, ultimo paso, geojson del mapa) se
agregan a partir de la Fase 4, una vez que existan los datos
estaticos (Fase 1) y el worker de polling (Fase 3).
"""

from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Sistema de monitoreo en tiempo real de Metrobus CDMX",
    version="0.1.0",
)

app.include_router(health.router)


@app.get("/")
async def root():
    return {
        "mensaje": f"{settings.app_name} corriendo",
        "docs": "/docs",
    }
