"""
Punto de entrada de la aplicacion.

En esta fase solo se registra el router de health-check. Las rutas de
negocio (estacion mas cercana, ultimo paso, geojson del mapa) se
agregan a partir de la Fase 4, una vez que existan los datos
estaticos (Fase 1) y el worker de polling (Fase 3).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import debug, health
from app.core.config import get_settings
from app.db.session import close_pool, init_models

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar: crea las tablas/extensiones si no existen.
    # Los datos estaticos (rutas/estaciones) se cargan aparte, una sola
    # vez, con scripts/cargar_gtfs_estatico.py -- no en cada arranque.
    await init_models()
    yield
    # Al apagar: cierra el pool de conexiones limpiamente.
    await close_pool()


app = FastAPI(
    title=settings.app_name,
    description="Sistema de monitoreo en tiempo real de Metrobus CDMX",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(debug.router)


@app.get("/")
async def root():
    return {
        "mensaje": f"{settings.app_name} corriendo",
        "docs": "/docs",
    }
