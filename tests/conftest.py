"""
Fixtures para todos los test.

El esquema se crea UNA SOLA VEZ al inicio de la sesión de pruebas.

Cada test recibe una conexión envuelta en una transacción que se
revierte al terminar. Esto es util para no tener que recrear tablas de prueba entre test

Flujo :
    1. pytest arranca
    2. setup_schema crea el esquema de prueba.
    3. cada test hace lo siguiente:
        - conn inicia una transacción.
        - client inyecta esa conexión en los endpoints.
        - El test corre.
        - La transacción se revierte, restaurando la BD.
    4. setup_schema limpia el esquema.

Dependencias:
    - pytest-asyncio.
    - asyncpg.
    - httpx.
"""

import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.db.schema import get_sentencias
from app.db.session import get_db
from app.main import app

settings = get_settings()


# Fixtures de base de datos
@pytest.fixture(scope="session")
async def db_pool():
    """
    Pool de conexiones a la base de datos de pruebas.

    Se crea una única instancia para toda la sesión de pruebas y se cierra
    al finalizar. La base de datos debe estar configurada en la variable
    de entorno DATABASE_TEST_URL.

    Yields:
        asyncpg.Pool: Pool de conexiones.

    Example:
        >>> async with db_pool.acquire() as conn:
        ...     result = await conn.fetchval("SELECT 1")
        ...     assert result == 1
    """
    pool = await asyncpg.create_pool(
        settings.database_test_url,
        min_size=1,
        max_size=3,
    )
    yield pool
    await pool.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_schema(db_pool):
    """
    Crea el esquema de la base de datos una vez al inicio de la sesión
    y lo limpia al finalizar.

    Esta fixture se ejecuta automáticamente y se encarga de:
        1. Eliminar el esquema existente y recrearlo.
        2. Ejecutar todo el ddl
        3. Limpiar el esquema nuevamente.

    Args:
        db_pool: Pool de conexiones a la base de datos.

    """
    async with db_pool.acquire() as conn:
        # Reset completo del esquema
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for stmt in get_sentencias():
            await conn.execute(stmt)
    yield
    # Limpieza al finalizar
    async with db_pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


@pytest.fixture
async def conn(db_pool, setup_schema):
    """
    Conexión a la base de datos envuelta en una transacción que se revierte
    al acabar el test.

    Cada test recibe una conexión que tiene una transacción activa. 
    Cualquier cambio que el test haga se revierte automaticamente.
    Con esto el estado de la BD es el mismo al inicio de cada test.

    Args:
        db_pool: Pool de conexiones.
        setup_schema: Dependencia.

    Yields:
        asyncpg.Connection: Conexión con transacción activa.

    Example:
        >>> async def test_algo(conn):
        ...     await conn.execute("INSERT INTO rutas ...")
        ...     # Al terminar, la transacción se revierte y la ruta no persiste.
    """
    async with db_pool.acquire() as connection:
        tx = connection.transaction()
        await tx.start()
        yield connection
        await tx.rollback()


# Fixtures de datos de prueba
@pytest.fixture
async def datos_base(conn):
    """
    Datos mínimos reutilizables para la mayoría de los tests.

    Esta fixture inserta un conjunto de datos de prueba básicos:
        - 2 rutas (r001, r002) que representan IDA y REGRESO de una misma línea.
        - 3 estaciones (Insurgentes, Álamos, La Raza)
          de la CDMX para que las consultas espaciales funcionen.
        - Relaciones ruta-estación con orden y sentido.

    Args:
        conn: Conexión a la base de datos.

    Example:
        >>> async def test_estaciones(conn, datos_base):
        ...     estaciones = await conn.fetch("SELECT * FROM estaciones")
        ...     assert len(estaciones) == 3
    """
    # Rutas
    await conn.executemany(
        """
        INSERT INTO rutas (route_id, nombre_corto, nombre_largo, color, agencia)
        VALUES ($1, $2, $3, $4, $5)
        """,
        [
            ("r001", "1", "Línea 1 IDA",     "D40D0D", "Metrobus"),
            ("r002", "1", "Línea 1 REGRESO", "D40D0D", "Metrobus"),
        ],
    )
    # Estaciones
    await conn.executemany(
        """
        INSERT INTO estaciones (stop_id, nombre, lat, lon, ubicacion)
        VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($4, $3), 4326)::geography)
        """,
        [
            ("est001", "Insurgentes", 19.4284, -99.1677),
            ("est002", "Álamos",      19.3947, -99.1429),
            ("est003", "La Raza",     19.4730, -99.1392),
        ],
    )
    # Relaciones ruta-estación
    await conn.executemany(
        """
        INSERT INTO ruta_estaciones (route_id, stop_id, sentido, orden)
        VALUES ($1, $2, $3, $4)
        """,
        [
            ("r001", "est001", "IDA", 1),
            ("r001", "est002", "IDA", 2),
            ("r002", "est002", "IDA", 1),
            ("r002", "est001", "IDA", 2),
        ],
    )


# Fixtures del cliente HTTP

@pytest.fixture
async def client(conn):
    """
    Cliente HTTP para probar los endpoints de FastAPI.

    sobrescribe la dependencia get_db de FastAPI para que
    los endpoints utilicen la misma conexión que el test.
    Esto asegura que las operaciones que hacen los endpoints (consultas,
    inserciones) vean exactamente los datos que el test ha preparado.

    La conexión se inyecta mediante app.dependency_overrides, que es la
    forma de FastAPI para mockear.

    Args:
        conn: Conexión a la base de datos.

    Yields:
        httpx.AsyncClient: Cliente HTTP.

    Example:
        >>> async def test_estacion_cercana(client, datos_base):
        ...     resp = await client.get("/estaciones/cercana?lat=19.4&lon=-99.1")
        ...     assert resp.status_code == 200
        ...     data = resp.json()
        ...     assert data["stop_id"] == "est001"
    """
    # Sobrescribir la dependencia get_db
    async def override_get_db():
        yield conn

    app.dependency_overrides[get_db] = override_get_db

    # Crear cliente con el transporte ASGI
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Limpiar overrides después del test
    app.dependency_overrides.clear()