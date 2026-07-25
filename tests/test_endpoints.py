"""
Tests de integración de los endpoints principales de consulta.

Estos tests verifican que los endpoints HTTP de la API funcionan correctamente.

Notas:
    - Usan la base de datos de pruebas real para validar
      consultas SQL/Postgis.
    - Cada test se ejecuta en una transacción que se revierte al final
      (gracias a los fixtures `conn` y `client` de conftest.py).
    - Se insertan datos de prueba (vía fixture `datos_base`) y se
      verifica que los endpoints devuelvan las respuestas esperadas.
    - Cubren casos buenos y de error (404, 422, etc.).

endpoints a probar:
    - GET /health - verifica que la app y la BD están operativas.
    - GET /estaciones/cercana - geolocalización y búsqueda espacial.
    - GET /estaciones/{stop_id}/estado - estado completo de una estación.
    - GET /estaciones/{stop_id}/ultimo-paso - último paso registrado.

"""

import pytest
from datetime import datetime, timezone


# Health endpoint

async def test_health(client):
    """
    Verifica que el endpoint /health responda correctamente.

    Comprueba que:
        - El endpoint devuelve 200 OK.
        - El status es "ok".
        - database_connected es True.

    Asegura que la aplicación está en funcionamiento.
    """
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database_connected"] is True


# Endpoint: estación más cercana (/estaciones/cercana)

async def test_estacion_cercana_devuelve_la_mas_proxima(client, datos_base):
    """
    Dadas coordenadas exactas de una estación, devuelve esa estación.

    Se utilizan las coordenadas de Insurgentes (est001) y se verifica
    que el endpoint devuelva stop_id "est001" y nombre "Insurgentes".

    La consulta usa el índice espacial GIST para
    encontrar la estación más cercana de forma eficiente.
    """
    resp = await client.get("/estaciones/cercana?lat=19.4284&lon=-99.1677")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_id"] == "est001"
    assert data["nombre"] == "Insurgentes"


async def test_estacion_cercana_sin_parametros(client):
    """
    La petición sin parámetros obligatorios devuelve 422 (Unprocessable Entity).

    FastAPI valida los parámetros de consulta,
    por lo que si faltan lat o lon, la respuesta es 422
    """
    resp = await client.get("/estaciones/cercana")
    assert resp.status_code == 422


# Endpoint: estado de estación (/estaciones/{stop_id}/estado)

async def test_estado_estacion_sin_pasos(client, datos_base):
    """
    Estado de una estación recién cargada, sin pasos aún.

    Debe devolver:
        - El nombre y stop_id de la estación.
        - Todas las rutas que pasan por ella.
        - Cada ruta debe tener ultimo_paso = None

    Verifica que la consulta devuelva las rutas incluso
    cuando no hay pasos registrados.
    """
    resp = await client.get("/estaciones/est001/estado")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_id"] == "est001"
    assert data["nombre"] == "Insurgentes"
    assert len(data["rutas"]) == 2
    for ruta in data["rutas"]:
        assert ruta["ultimo_paso"] is None


async def test_estado_estacion_refleja_ultimo_paso(client, datos_base, conn):
    """
    Tras registrar un paso, el estado debe mostrarlo en la ruta correspondiente.

    Se inserta un paso para la ruta r001 en la estación est001.
    Luego se consulta el estado y se verifica que:
        - La ruta r001 tiene ultimo_paso con vehicle_id y label correctos.
        - La ruta r002 (sin paso) tiene ultimo_paso = None.
    """
    await conn.execute(
        """
        INSERT INTO pasos_registrados
            (estacion_id, route_id, vehicle_id, label, detectado_en)
        VALUES ($1, $2, $3, $4, $5)
        """,
        "est001", "r001", "v001", "1234",
        datetime.now(timezone.utc),
    )

    resp = await client.get("/estaciones/est001/estado")
    assert resp.status_code == 200
    data = resp.json()

    ruta_con_paso = next(r for r in data["rutas"] if r["route_id"] == "r001")
    assert ruta_con_paso["ultimo_paso"] is not None
    assert ruta_con_paso["ultimo_paso"]["vehicle_id"] == "v001"
    assert ruta_con_paso["ultimo_paso"]["label"] == "1234"

    ruta_sin_paso = next(r for r in data["rutas"] if r["route_id"] == "r002")
    assert ruta_sin_paso["ultimo_paso"] is None


async def test_estado_estacion_no_encontrada(client):
    """
    Consultar una estación con stop_id inexistente devuelve 404.

    """
    resp = await client.get("/estaciones/no_existe/estado")
    assert resp.status_code == 404


# Endpoint: último paso (/estaciones/{stop_id}/ultimo-paso)

async def test_ultimo_paso_sin_registros(client, datos_base):
    """
    Consultar el último paso de una estación sin pasos devuelve 404.
    
    """
    resp = await client.get("/estaciones/est001/ultimo-paso?route_id=r001")
    assert resp.status_code == 404


async def test_ultimo_paso_devuelve_datos_correctos(client, datos_base, conn):
    """
    Con un paso registrado, devuelve la estación, ruta y vehículo correctos.

    Se inserta un paso y se consulta el endpoint. Se verifica que:
        - El status code es 200.
        - Los campos estacion_id, route_id, vehicle_id y label coinciden
          con los datos insertados.
    """
    await conn.execute(
        """
        INSERT INTO pasos_registrados
            (estacion_id, route_id, vehicle_id, label, detectado_en)
        VALUES ($1, $2, $3, $4, $5)
        """,
        "est001", "r001", "v001", "1234",
        datetime.now(timezone.utc),
    )

    resp = await client.get("/estaciones/est001/ultimo-paso?route_id=r001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["estacion_id"] == "est001"
    assert data["route_id"] == "r001"
    assert data["vehicle_id"] == "v001"
    assert data["label"] == "1234"