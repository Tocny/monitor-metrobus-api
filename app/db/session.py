"""
Configuracion de la conexion async a la base de datos.

En Fase 0 esto solo deja la plomeria lista (engine + sesion async).
Los modelos (rutas, estaciones, pasos_registrados) se agregan en Fase 1,
y ahi mismo se definira la base declarativa y las migraciones.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency de FastAPI para obtener una sesion de base de datos por request."""
    async with AsyncSessionLocal() as session:
        yield session


async def check_db_connection() -> bool:
    """Usado por el endpoint /health para confirmar que la base responde."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
