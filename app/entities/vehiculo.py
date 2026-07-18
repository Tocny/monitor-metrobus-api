"""
Entidades de vehículo.

Define dos modelos principales:
    1. Vehiculo: Representa un vehículo tal como viene del feed GTFS-RT
    2. VehiculoActual: Representa un vehículo tal como está guardado en
       la base de datos (última posición conocida).

La separación es importante porque:
    - El feed GTFS-RT tiene un timestamp (epoch) y NO tiene
      estacion_actual_id (eso lo averigua la aplicación).
    - La BD tiene un timestamp de actualización (actualizado_en) y
      agrega el campo estacion_actual_id después del procesamiento.

Relación:
    - Un Vehiculo del feed se transforma en un VehiculoActual
      después de pasar por el worker de polling (que calcula
      la estación actual y agrega el timestamp de actualización).
"""

from datetime import datetime

from pydantic import BaseModel


class Vehiculo(BaseModel):
    """
    Vehículo tal como viene del feed GTFS-RT.

    Esta entidad se usa para recibir datos del feed que descarga
    el cliente HTTP (metrobus_client). Es la representación "normal" de
    un vehículo, sin ningún procesamiento adicional.

    Attributes:
        vehicle_id: Identificador único del vehículo en el feed GTFS-RT.
        label: Número visible del autobús.
        route_id: Identificador de la ruta que está recorriendo el
            vehículo
        lat: Latitud en grados decimales.
        lon: Longitud en grados decimales.
        velocidad: Velocidad del vehículo en m/s.
        timestamp: Timestamp UNIX de la posición reportada por el feed. 
            Es el momento en que el vehículo reportó su posición.

    Note:
        Esta entidad NO contiene `estacion_actual_id` ni `actualizado_en`
        porque esos campos son calculados por la aplicación (el worker).

    Example:
        >>> from app.services.metrobus_client import obtener_vehiculos_actuales
        >>> vehiculos = await obtener_vehiculos_actuales()
        >>> v = vehiculos[0]
        >>> print(f"{v.vehicle_id} en ({v.lat}, {v.lon})")
    """
    vehicle_id: str
    label: str | None = None
    route_id: str | None = None
    lat: float
    lon: float
    velocidad: float | None = None
    timestamp: int


class VehiculoActual(BaseModel):
    """
    Vehículo tal como está guardado en la base de datos (última posición).

    Esta entidad se usa para leer/escribir en la tabla `vehiculos_actuales`.
    Contiene la última posición conocida de cada vehículo, enriquecida
    con información calculada por la aplicación (estación actual) y
    info de la BD (timestamp de actualización).

    Es el resultado de transformar un Vehiculo (del feed) en un modelo
    persistente, agregando:
        - estacion_actual_id: La estación en cuyo radio se encuentra
          el vehículo (calculado por el worker).
        - actualizado_en: Marca de tiempo (UTC) de cuándo se actualizó
          este registro en la BD.

    Attributes:
        vehicle_id: Identificador único del vehículo (clave primaria).
        label: Número visible del autobús
        route_id: Identificador de la ruta .
        lat: Latitud en grados decimales de la última posición reportada.
        lon: Longitud en grados decimales de la última posición reportada.
        velocidad: Velocidad en m/s
        feed_timestamp: Timestamp UNIX de la posición reportada.
        estacion_actual_id: Identificador de la estación en cuyo radio
            se encuentra el vehículo. Es None si el vehículo está en
            movimiento entre estaciones.
        actualizado_en: Marca de tiempo (UTC) de cuándo se actualizó
            este registro en la base de datos (generada por la BD al
            hacer el UPSERT).

    Note:
        La diferencia clave entre Vehiculo y VehiculoActual es:
            - Vehiculo: no tiene estacion_actual_id ni actualizado_en.
            - VehiculoActual: tiene ambos, y feed_timestamp (en lugar
              de timestamp) para reflejar que proviene del feed.

    Example:
        >>> from app.repositories.vehiculos_repository import upsert_vehiculo
        >>> vehiculo_actual = VehiculoActual(
        ...     vehicle_id="69379",
        ...     label="1203",
        ...     route_id="19429",
        ...     lat=19.467312,
        ...     lon=-99.140939,
        ...     velocidad=5.0,
        ...     feed_timestamp=1781755570,
        ...     estacion_actual_id="fa078a",
        ...     actualizado_en=datetime.now(timezone.utc)
        ... )
        >>> await upsert_vehiculo(conn, vehiculo_actual)
    """
    vehicle_id: str
    label: str | None = None
    route_id: str | None = None
    lat: float
    lon: float
    velocidad: float | None = None
    feed_timestamp: int
    estacion_actual_id: str | None = None
    actualizado_en: datetime | None = None