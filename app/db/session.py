"""
Conexión a PostgreSQL via asyncpg.

Este módulo gestiona el pool de conexiones a la base de datos PostgreSQL
utilizando asyncpg. Proporciona funciones para obtener
conexiones, inicializar el esquema, verificar
el estado de la base de datos, y cerrar el pool al bajar el servicio.

El patrón de uso es:
    1. get_pool(): obtiene o crea el pool de conexiones.
    2. get_db(): dependencia de FastAPI que proporciona una conexión por request.
    3. init_models(): crea las tablas y extensiones necesarias si no existen.
    4. close_pool(): cierra el pool durante el apagado.

Características:
    - Pool de conexiones.
    - Reutilización de conexiones.
    - Manejo asíncrono con async/await.

Dependencias:
    - asyncpg 
    - app.core.config 
    - app.db.schema 
"""

from collections.abc import AsyncGenerator

import asyncpg

from app.core.config import get_settings
from app.db.schema import DDL_SQL

# Configuración
settings = get_settings()

# Pool de conexiones
_pool: asyncpg.Pool | None = None


# Funciones para gestión del pool.

async def get_pool() -> asyncpg.Pool:
    """
    Crea y devuelve el pool de conexiones a la base de datos.

    El pool se inicializa la primera vez que se llama a esta función.
    Las siguientes llamadas devuelven el mismo pool ya creado.

    Se configura con:
        - min_size=1: mantiene al menos una conexión abierta.
        - max_size=5: límite máximo de conexiones concurrentes.

    Returns:
        asyncpg.Pool: Pool de conexiones a PostgreSQL.

    Example:
        >>> pool = await get_pool()
        >>> async with pool.acquire() as conn:
        ...     await conn.execute("SELECT 1")
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
        )
    return _pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Dependencia de FastAPI: proporciona una conexión del pool por request.

    Esta función está diseñada para ser usada como dependencia en los
    endpoints de FastAPI. Cada request obtiene su propia conexión del
    pool y la libera al finalizar.

    Yields:
        asyncpg.Connection: Conexión a PostgreSQL.

    Example:
        >>> @app.get("/estaciones")
        ... async def listar_estaciones(conn: asyncpg.Connection = Depends(get_db)):
        ...     return await conn.fetch("SELECT * FROM estaciones")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# Funciones auxiliares para mantenimiento y diagnóstico

async def check_db_connection() -> bool:
    """
    Verifica que la base de datos esté accesible y responda a consultas.

    Se usa principalmente en `/health` para monitoreo y
    diagnóstico. Retorna True si la conexión es exitosa, 
    False en caso de error.

    Returns:
        bool: True si la base de datos responde correctamente, False si no.

    Example:
        >>> if await check_db_connection():
        ...     print("Base de datos disponible")
        ... else:
        ...     print("Error de conexión")
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def init_models() -> None:
    """
    Crea las tablas, índices y extensiones necesarias si no existen.

    Esta función ejecuta el DDL definido en app/db/schema.py 
    Se puede ejecutar n veces sin causar errores o duplicar estructuras

    Se debe llamar al levantar la api para asegurar que la base de datos esté lista.

    Raises:
        asyncpg.PostgresError: Si falla la ejecución del DDL 
        
    Example:
        >>> await init_models()
        # Tablas y extensiones creadas/verificadas.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(DDL_SQL)


async def close_pool() -> None:
    """
    Cierra el pool de conexiones de forma segura.

    Esta función debe ser llamada durante el sutdown para liberar los recursos.

    Después de cerrar el pool, la variable global `_pool` se establece
    a `None` para permitir que se vuelva a crear si la aplicación
    se reinicia.

    Example:
        >>> # En main.py, dentro del lifespan:
        ... @asynccontextmanager
        ... async def lifespan(app):
        ...     await init_models()
        ...     yield
        ...     await close_pool()
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None