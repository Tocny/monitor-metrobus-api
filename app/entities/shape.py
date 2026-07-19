"""
Entidad ShapePunto (punto de trazado geométrico de ruta).

Representa un punto individual de la polilínea que forma el trazado
geográfico de una ruta. Los puntos se unen en orden de secuencia para
dibujar la línea exacta que sigue el Metrobús en el mapa.

Estos puntos provienen del archivo shapes.txt del GTFS estático.

Relaciones:
    - Un ShapePunto pertenece a una ruta.
    - Cada ruta tiene múltiples ShapePuntos, ordenados por secuencia.

Uso:
    - Dibujar la ruta en el frontend.
    - Calcular distancias sobre el trazado real.

Dependencias:
    - Pydantic.
"""

from pydantic import BaseModel


class ShapePunto(BaseModel):
    """
    Punto de trazado geográfico que forma parte de la línea de una ruta.

    Attributes:
        route_id: Identificador de la ruta a la que pertenece el punto
        secuencia: Orden del punto en la polilínea.
        lat: Latitud del punto en grados decimales.
        lon: Longitud del punto en grados decimales.

    Example:
        >>> punto = ShapePunto(
        ...     route_id="19429",
        ...     secuencia=1,
        ...     lat=19.467312,
        ...     lon=-99.140939
        ... )
        >>> print(f"Punto {punto.secuencia}: ({punto.lat}, {punto.lon})")
        Punto 1: (19.467312, -99.140939)
    """
    route_id: str
    secuencia: int
    lat: float
    lon: float