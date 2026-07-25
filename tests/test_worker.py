"""
Tests unitarios de la lógica de detección de pasos en worker.py.

Aquí probamos la función _detectar_paso, que
determina cuándo un vehículo ha "pasado" por una estación y debe
registrar un paso en la base de datos.

Se hace de modo que :
    - Se mockean todos los repositorios (get_vehiculo, get_estaciones_de_ruta,
      insertar_paso) para aislar la lógica de negocio de la base de datos.
    - Cada test verifica un escenario distinto de la transición
      FUERA - DENTRO del radio de una estación.

Casos cubiertos:
    1. Primer paso de un vehículo (no habian registros en BD).
    2. Vehículo que ya estaba en la estación (evita duplicados).
    3. Vehículo fuera del radio de todas las estaciones.
    4. Vehículo sin route_id.
    5. Caché de estaciones por ruta.

Dependencias:
    - pytest.
    - unittest.mock.
    - app.services.worker._detectar_paso.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.entities.estacion import Estacion
from app.entities.paso import PasoRegistrado
from app.entities.vehiculo import VehiculoActual
from app.services.worker import _detectar_paso


# Fixtures locales

@pytest.fixture
def vehiculo_en_insurgentes():
    """
    Vehículo posicionado sobre la estación Insurgentes.
    """
    return VehiculoActual(
        vehicle_id="v001",
        label="1234",
        route_id="r001",
        lat=19.4284,
        lon=-99.1677,
        feed_timestamp=1_000_000,
        actualizado_en=datetime.now(timezone.utc),
    )


@pytest.fixture
def estacion_insurgentes():
    """Estación de prueba: Insurgentes."""
    return Estacion(stop_id="est001", nombre="Insurgentes", lat=19.4284, lon=-99.1677)


@pytest.fixture
def estacion_alamos():
    """Estación de prueba: Álamos."""
    return Estacion(stop_id="est002", nombre="Álamos", lat=19.3947, lon=-99.1429)


# Tests

async def test_paso_confirmado_primera_vez(
    conn, vehiculo_en_insurgentes, estacion_insurgentes, mocker
):
    """
    Escenario: Vehículo visto por primera vez dentro del radio de una estación.

    Cuando un vehículo aparece por primera vez en el sistema (no hay registro
    previo en vehiculos_actuales) y está dentro del radio de una estación,
    se debe registrar un paso.

    Comportamiento esperado:
        - get_vehiculo retorna None.
        - get_estaciones_de_ruta retorna la estación correspondiente.
        - insertar_paso se llama exactamente una vez con los datos correctos.
    """
    mocker.patch("app.services.worker.get_vehiculo", return_value=None)
    mocker.patch(
        "app.services.worker.get_estaciones_de_ruta",
        return_value=[estacion_insurgentes],
    )
    mock_insertar = mocker.patch(
        "app.services.worker.insertar_paso", new_callable=AsyncMock
    )

    await _detectar_paso(conn, vehiculo_en_insurgentes, {})

    mock_insertar.assert_called_once()
    paso: PasoRegistrado = mock_insertar.call_args[0][1]
    assert paso.estacion_id == "est001"
    assert paso.vehicle_id == "v001"
    assert paso.route_id == "r001"


async def test_sin_duplicado_si_ya_estaba_en_la_estacion(
    conn, vehiculo_en_insurgentes, estacion_insurgentes, mocker
):
    """
    Escenario: Vehículo que ya estaba en la misma estación en la lectura anterior.

    Este es el caso para evitar duplicados. Si el vehículo ya
    estaba dentro del radio de la estación en el ciclo anterior, no debe
    registrar un nuevo paso. De lo contrario, se registraría un paso
    cada 30 segundos mientras el vehículo esté detenido en la estación.

    Comportamiento esperado:
        - get_vehiculo retorna un vehículo con estacion_actual_id = "est001".
        - insertar_paso NO se llama.
    """
    vehiculo_anterior = VehiculoActual(
        vehicle_id="v001",
        route_id="r001",
        lat=19.4284,
        lon=-99.1677,
        feed_timestamp=999_999,
        estacion_actual_id="est001",  # Ya estaba aquí
        actualizado_en=datetime.now(timezone.utc),
    )
    mocker.patch("app.services.worker.get_vehiculo", return_value=vehiculo_anterior)
    mocker.patch(
        "app.services.worker.get_estaciones_de_ruta",
        return_value=[estacion_insurgentes],
    )
    mock_insertar = mocker.patch(
        "app.services.worker.insertar_paso", new_callable=AsyncMock
    )

    await _detectar_paso(conn, vehiculo_en_insurgentes, {})

    mock_insertar.assert_not_called()


async def test_sin_paso_fuera_de_radio(
    conn, vehiculo_en_insurgentes, estacion_alamos, mocker
):
    """
    Escenario: Vehículo lejos de todas las estaciones de su ruta.

    Si el vehículo está a más de 70 metros de todas las estaciones de su ruta,
    no se debe registrar ningún paso. En este caso, el vehículo está en
    Insurgentes pero la única estación de su ruta es Álamos.

    Comportamiento esperado:
        - get_estaciones_de_ruta retorna solo la estación Álamos.
        - insertar_paso NO se llama.
    """
    mocker.patch("app.services.worker.get_vehiculo", return_value=None)
    mocker.patch(
        "app.services.worker.get_estaciones_de_ruta",
        return_value=[estacion_alamos],  # Álamos está a ~4km
    )
    mock_insertar = mocker.patch(
        "app.services.worker.insertar_paso", new_callable=AsyncMock
    )

    await _detectar_paso(conn, vehiculo_en_insurgentes, {})

    mock_insertar.assert_not_called()


async def test_sin_paso_sin_route_id(conn, mocker):
    """
    Escenario: Vehículo sin route_id.

    En el feed GTFS-RT, ocasionalmente llegan vehículos que no tienen
    asignada una ruta. En ese caso, no se puede determinar
    qué estaciones evaluar, por lo que no se debe registrar ningún paso.

    Comportamiento esperado:
        - get_estaciones_de_ruta NO se llama (porque no hay route_id).
        - insertar_paso NO se llama.
    """
    vehiculo_sin_ruta = VehiculoActual(
        vehicle_id="v002",
        route_id=None,
        lat=19.4284,
        lon=-99.1677,
        feed_timestamp=1_000_000,
        actualizado_en=datetime.now(timezone.utc),
    )
    mock_insertar = mocker.patch(
        "app.services.worker.insertar_paso", new_callable=AsyncMock
    )

    await _detectar_paso(conn, vehiculo_sin_ruta, {})

    mock_insertar.assert_not_called()


async def test_cache_evita_queries_repetidas(
    conn, vehiculo_en_insurgentes, estacion_insurgentes, mocker
):
    """
    Escenario: Verificación de caché de estaciones por ruta.

    El worker usa un caché en memoria para almacenar
    las estaciones de cada ruta durante un ciclo de polling. Esto evita
    consultar la base de datos repetidamente por cada vehículo de la
    misma ruta.

    Optimización esperada:
        - Sin caché: 836 consultas (una por vehículo).
        - Con caché: 88 consultas (una por ruta).

    Comportamiento esperado:
        - get_estaciones_de_ruta se llama UNA SOLA VEZ a pesar de
          procesar dos vehículos de la misma ruta.
    """
    mocker.patch("app.services.worker.get_vehiculo", return_value=None)
    mock_get_estaciones = mocker.patch(
        "app.services.worker.get_estaciones_de_ruta",
        return_value=[estacion_insurgentes],
    )
    mocker.patch("app.services.worker.insertar_paso", new_callable=AsyncMock)

    cache = {}
    vehiculo_2 = VehiculoActual(
        vehicle_id="v002",
        label="5678",
        route_id="r001", 
        lat=19.4284,
        lon=-99.1677,
        feed_timestamp=1_000_001,
        actualizado_en=datetime.now(timezone.utc),
    )

    await _detectar_paso(conn, vehiculo_en_insurgentes, cache)
    await _detectar_paso(conn, vehiculo_2, cache)

    assert mock_get_estaciones.call_count == 1