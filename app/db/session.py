"""
Conexion a PostgreSQL via asyncpg -- SQL directo, sin ORM.

Funciona igual apuntando al Postgres local (docker-compose, para
desarrollo) o a Supabase (para produccion): solo cambia el valor de
DATABASE_URL en .env, el codigo no se entera de la diferencia.
"""

from collections.abc import AsyncGenerator

import asyncpg

from app.core.config import get_settings
from app.db.schema import DDL_SQL

settings = get_settings()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Crea el pool de conexiones la primera vez que se necesita (lazy)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,  # de sobra para esta escala; Supabase free permite hasta 60 directas
        )
    return _pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency de FastAPI: una conexion del pool por request."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def check_db_connection() -> bool:
    """Usado por el endpoint /health para confirmar que la base responde."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def init_models() -> None:
    """Crea las tablas y extensiones si no existen (idempotente)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(DDL_SQL)


async def close_pool() -> None:
    """Cierra el pool limpiamente al apagar la app (ver lifespan en main.py)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
