"""
Entidad que representa un paso registrado de un vehículo por una estación.

Cada instancia de `PasoRegistrado` corresponde a un evento confirmado
en el que un autobús pasó por una estación en un momento específico.
(cuando un vehículo entra en el radio de una estación) y se almacenan 
en la tabla `pasos_registrados` de la base de datos.

Esta entidad se utiliza en:
    - El worker de polling 
    - Los repositorios (
    - Los endpoints

"""

from datetime import datetime

from pydantic import BaseModel


class PasoRegistrado(BaseModel):
    """
    Registro de un evento de paso de un vehículo por una estación.

    Representa un hecho confirmado: el vehículo `vehicle_id` (con
    número visible `label`) pasó por la estación `estacion_id` de la
    ruta `route_id` en el momento `detectado_en`.

    Attributes:
        id: Identificador único del registro en la base de datos.
        estacion_id: Identificador de la estación (stop_id) donde se registró el paso.
        route_id: Identificador de la ruta (route_id) en la que circulaba el vehículo en el momento del paso.
        vehicle_id: Identificador único del vehículo
        label: Número visible del autobús.
        detectado_en: timestamp del momento en que se detectó el paso. 

    Example:
        >>> paso = PasoRegistrado(
        ...     estacion_id="fa078a",
        ...     route_id="19429",
        ...     vehicle_id="69379",
        ...     label="1203",
        ...     detectado_en=datetime.now(timezone.utc)
        ... )
        >>> # Antes de insertar en BD, el id es None
        >>> print(paso.id)
        None
        >>> # Después de insertar, el repositorio actualiza el objeto
        >>> # con el id generado por la base de datos.
    """
    id: int | None = None
    estacion_id: str
    route_id: str
    vehicle_id: str
    label: str | None = None
    detectado_en: datetime