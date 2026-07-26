"""
Fixtures para todos los tests.

    - El esquema se crea al inicio, de forma sincrona (antes de que pytest-asyncio tome
      control de los event loops). Esto evita el error de ScopeMismatch cuando no se
      ponen de acuerdo session con function

    - Cada test recibe una conexión directa a la base de datos envuelta en una transacción
      que se revierte al terminar. Esto garantiza que test aislados.

    - El cliente HTTP sobrescribe la dependencia get_db para usar
      exactamente la misma conexión que el test, para que los endpoints
      vean los datos preparados para testing.

Dependencias:
    - pytest 
    - pytest-asyncio 
    - asyncpg 
    - httpx 
    - FastAPI
"""

import asyncio

import asyncpg
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.db.schema import get_sentencias
from app.db.session import get_db
from app.main import app

settings = get_settings()


# Creación del schema.

async def _inicializar_schema() -> None:
    """
    Crea y configura el esquema de la base de datos de pruebas.

    Esta función se ejecuta una sola vez utilizando asyncio.run() para crear un event loop.
        - Se ejecuta antes de que pytest-asyncio cree sus event loops.
        - Evita el `ScopeMismatch` de sesión y de función.

    Operaciones realizadas:
        1. Elimina el esquema public existente y lo recrea vacío.
        2. Ejecuta todas las sentencias DDL

    Raises:
        asyncpg.exceptions.PostgresError: Si falla la conexión o la ejecución
            de las sentencias SQL.
    """
    conn = await asyncpg.connect(settings.database_test_url)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for stmt in get_sentencias():
            await conn.execute(stmt)
    finally:
        await conn.close()


# Ejecución síncrona al importar el módulo
asyncio.run(_inicializar_schema())


# Fixtures de base de datos

@pytest.fixture
async def conn():
    """
    Conexión directa a la base de datos para un test individual.

    Esta fixture proporciona una conexión activa a PostgreSQL que:
        - Se crea para el test que la solicita.
        - Inicia una transacción al principio del test.
        - Revierte la transacción al finalizar.
        - Cierra la conexión.

    Nota: no usamos pool de conexiones porque generaba conflcitos con el event loop.

    Yields:
        asyncpg.Connection:  conexion a la bd de testing.

    Example:
        >>> async def test_algo(conn):
        ...     # Los datos insertados solo viven dentro de este test
        ...     await conn.execute("INSERT INTO rutas ...")
        ...     # Al terminar, la transacción se revierte y la ruta no persiste
    """
    connection = await asyncpg.connect(settings.database_test_url)
    tx = connection.transaction()
    await tx.start()
    yield connection
    await tx.rollback()
    await connection.close()


@pytest.fixture
async def datos_base(conn):
    """
    Datos reutilizables para la mayoría de los tests.

    Esta fixture inserta un conjunto de datos de prueba básicos que son
    comunes a muchos tests. Se revierten al finalizar el test.

    Datos insertados:
        - 2 rutas: `r001` (IDA) y `r002` (REGRESO) de la misma línea.
        - 3 estaciones: Insurgentes, Álamos y La Raza, con coordenadas
          reales de la CDMX para que las consultas espaciales (PostGIS)
          funcionen correctamente.
        - Relaciones ruta-estación con orden y sentido, para que los
          endpoints de "estado de estación" y "último paso" tengan
          datos con los que trabajar.

    Args:
        conn: Conexión a la base de datos.

    Example:
        >>> async def test_estaciones(conn, datos_base):
        ...     estaciones = await conn.fetch("SELECT * FROM estaciones")
        ...     assert len(estaciones) == 3
    """
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


# Cliente HTTP

@pytest.fixture
async def client(conn):
    """
    Cliente HTTP para probar los endpoints.

    Este fixture sobrescribe la dependencia get_db para
    que los endpoints utilicen exactamente la misma conexión que el test.
    Así los endpoints ven los datos de prueba y las consultas se pueden revertir,
    además de que un test tiene conexión individual para aislarlo.

    Args:
        conn: Conexión a la base de datos.

    Yields:
        httpx.AsyncClient: Cliente HTTP asíncrono para interactuar con
        la API. Las peticiones se envían a `http://test`

    Example:
        >>> async def test_estacion_cercana(client, datos_base):
        ...     resp = await client.get("/estaciones/cercana?lat=19.4&lon=-99.1")
        ...     assert resp.status_code == 200
        ...     data = resp.json()
        ...     assert data["stop_id"] == "est001"
    """
    async def override_get_db():
        yield conn

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()