"""
Punto de entrada de la aplicacion.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import debug, health
from app.controllers import estaciones_controller, mapa_controller, pasos_controller
from app.core.config import get_settings
from app.db.session import close_pool, init_models
from app.services.worker import detener_worker, iniciar_worker

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    await iniciar_worker()
    yield
    await detener_worker()
    await close_pool()


app = FastAPI(
    title=settings.app_name,
    description="Sistema de monitoreo en tiempo real de Metrobus CDMX",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(estaciones_controller.router)
app.include_router(pasos_controller.router)
app.include_router(mapa_controller.router)


@app.get("/")
async def root():
    return {
        "mensaje": f"{settings.app_name} corriendo",
        "docs": "/docs",
    }