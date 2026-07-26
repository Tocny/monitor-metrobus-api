"""
Tests unitarios de app/services/geo.py.

Este módulo contiene pruebas para la función de cálculo de distancia
Haversine. Son pruebas puramente matemáticas y deterministas.

Las pruebas verifican:
    - Casos extremos (mismo punto → distancia = 0).
    - Escenarios de proximidad (dentro/fuera del radio de 70 metros).
    - Rango esperado para distancias conocidas.
    - Pruebas de congruencia matematica como simetria.
"""

from app.services.geo import distancia_metros


def test_mismo_punto_da_cero():
    """
    Verifica que la distancia entre un punto y sí mismo sea exactamente 0.

    """
    assert distancia_metros(19.4284, -99.1677, 19.4284, -99.1677) == 0.0


def test_dentro_del_radio_de_70_metros():
    """
    Verifica que un desplazamiento de ~22 metros
    esté dentro del radio de 70 metros configurado en el sistema.

    Esto es crítico porque el worker usa este umbral para detectar si
    un vehículo está en una estación. 
    """
    # Desplazamiento de ~0.0002 grados en latitud ≈ 22 metros
    dist = distancia_metros(19.4284, -99.1677, 19.4286, -99.1677)
    assert dist < 70


def test_fuera_del_radio_de_70_metros():
    """
    Verifica que la distancia entre Insurgentes y Álamos (~4 km) sea
    claramente superior al radio de 70 metros.

    """
    # Insurgentes - Álamos ≈ 4km
    dist = distancia_metros(19.4284, -99.1677, 19.3947, -99.1429)
    assert dist > 70


def test_distancia_en_rango_esperado():
    """
    Valida que la distancia entre Insurgentes y La Raza esté en el
    rango esperado para la Ciudad de México.

    Esta prueba es útil para detectar cambios en la fórmula de Haversine
    o su configuracion.
    """
    # Insurgentes - La Raza ≈ 5km
    dist = distancia_metros(19.4284, -99.1677, 19.4730, -99.1392)
    assert 4000 < dist < 7000


def test_simetria():
    """
    Verifica que la función de distancia sea simétrica.

    La distancia de A a B debe ser igual a la distancia de B a A.
    """
    d1 = distancia_metros(19.4284, -99.1677, 19.3947, -99.1429)
    d2 = distancia_metros(19.3947, -99.1429, 19.4284, -99.1677)
    assert abs(d1 - d2) < 0.001