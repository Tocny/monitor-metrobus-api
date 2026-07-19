"""
Utilidad geométrica.

Proporciona funciones de cálculo geográfico.

Usada por:
    - app/services/worker.py
"""

import math


def distancia_metros(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calcula la distancia en metros entre dos puntos geográficos usando
    la fórmula de Haversine.

    La fórmula de Haversine es adecuada para distancias cortas y
    medianas (< 1000 km).

    Args:
        lat1: Latitud del punto 1 en grados decimales.
        lon1: Longitud del punto 1 en grados decimales.
        lat2: Latitud del punto 2 en grados decimales.
        lon2: Longitud del punto 2 en grados decimales.

    Returns:
        Distancia en metros entre los dos puntos.

    Example:
        >>> # Distancia entre dos puntos idénticos = 0
        >>> distancia_metros(19.4326, -99.1332, 19.4326, -99.1332)
        0.0

        >>> # Distancia aproximada entre el Zócalo y la estación Insurgentes
        >>> distancia_metros(19.4326, -99.1332, 19.423, -99.165)
        3336.42  

    Note:
        - Todos los ángulos deben estar en grados decimales.
        - El orden de los puntos no afecta el resultado .
        - El resultado es en metros.
    """
    R = 6_371_000  # radio medio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(a))