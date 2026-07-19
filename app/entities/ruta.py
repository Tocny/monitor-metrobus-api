"""
Entidad que representa una ruta del Metrobús.

Son datos estáticos que se cargan desde el GTFS
y se almacenan en la tabla `rutas`. Cada ruta tiene un identificador
único (`route_id`) que la vincula con:
    - Las estaciones que la componen (ruta_estaciones).
    - Los puntos de su trazo geográfico (shapes).
    - Los pasos de vehículos (pasos_registrados).
    - Los vehículos en movimiento (vehiculos_actuales).

Esta entidad se utiliza en los repositorios para mapear los resultados
de las consultas SQL y en la API para devolver información de las rutas.
"""

from pydantic import BaseModel


class Ruta(BaseModel):
    """
    Representa una ruta del Metrobús.

    Contiene la información básica de una ruta, incluyendo su
    identificador, nombres, color y agencia.

    Attributes:
        route_id: Identificador único de la ruta en el GTFS.
        nombre_corto: Número de la ruta, tal como la conoce el usuario.
        nombre_largo: Descripción extendida de la ruta.
        color: Código de color en formato hexadecimal
        agencia: Nombre de la agencia que opera la ruta.

    Example:
        >>> ruta = Ruta(
        ...     route_id="19429",
        ...     nombre_corto="3",
        ...     nombre_largo="L03d03-1 tenayuca - la raza",
        ...     color="7A9A01",
        ...     agencia="Metrobus"
        ... )
        >>> print(ruta.nombre_corto)
        '3'
    """
    route_id: str
    nombre_corto: str | None = None
    nombre_largo: str | None = None
    color: str | None = None
    agencia: str | None = None