"""
Utilidad geometrica pura (sin dependencias del proyecto).

Recibe y devuelve tipos primitivos a proposito -- no depende de
entidades ni de ninguna otra capa, lo que la hace facil de testear
y reutilizable sin riesgo de imports circulares.

Usada por: app/services/worker.py
"""

import math


def distancia_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distancia en metros entre dos puntos GPS usando la formula de
    Haversine. Precision suficiente para distancias cortas (<1km)
    como las que manejamos al detectar si un camion esta dentro del
    radio de una estacion (~70 metros).
    """
    R = 6_371_000  # radio medio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

    return 2 * R * math.asin(math.sqrt(a))