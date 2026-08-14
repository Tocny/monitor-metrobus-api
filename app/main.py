"""
Punto de entrada de la aplicacion.
"""

from contextlib import asynccontextmanager

import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded


from app.api.routes import debug, health
from app.controllers import estaciones_controller, mapa_controller, pasos_controller
from app.core.config import get_settings
from app.db.session import close_pool, init_models
from app.services.worker import detener_worker, iniciar_worker

settings = get_settings()

# Config de login
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Rate limiter de todos los endpoints: 100 peticiones por minuto por IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


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
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)

# Config rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Config de cors
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]
if settings.environment == "development":
    ALLOWED_ORIGINS.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Config del middleware de loggin.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"{request.client.host} - {request.method} {request.url.path} "
        f"{response.status_code} - {process_time:.3f}s"
    )
    return response

#Config rutas
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