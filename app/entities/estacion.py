"""
Entidades relacionadas con estaciones.

Este módulo define los objetos de transferencia de datos y
modelos de dominio que representan estaciones, rutas y el estado
combinado de una estación (incluyendo el último paso de vehículos).

Todas las clases heredan de Pydantic BaseModel,
principalmente para validar datos y generar el JSON agilmente.

Estas entidades son utilizadas por:
    - Los repositorios.
    - Los servicios.
    - Los endpoints de la API.
"""

from datetime import datetime

from pydantic import BaseModel


# Entidad base: Estación

class Estacion(BaseModel):
    """
    Representa una estación física del Metrobús.

    Contiene la información geográfica y el identificador único de la
    estación, tal como se define en el GTFS estático (stop_id).

    Attributes:
        stop_id: Identificador único de la estación en el GTFS.
        nombre: Nombre de la estación.
        lat: Latitud en grados decimales.
        lon: Longitud en grados decimales.

    Example:
        >>> estacion = Estacion(
        ...     stop_id="fa078a",
        ...     nombre="Insurgentes",
        ...     lat=19.423,
        ...     lon=-99.165
        ... )
        >>> print(estacion.model_dump_json())
    """
    stop_id: str
    nombre: str
    lat: float
    lon: float



# Entidades para el endpoint /estaciones/{stop_id}/estado 

class UltimoPasoResumen(BaseModel):
    """
    Resumen del último paso de un vehículo por una estación.

    Se utiliza dentro de `RutaConUltimoPaso` para mostrar, para cada
    ruta que pasa por una estación, cuándo fue el último paso y qué
    vehículo lo realizó.

    Attributes:
        vehicle_id: Identificador del vehículo.
        label: Número visible del autobús.
        detectado_en: Marca de tiempo (UTC) del momento en que se
            registró el paso en la base de datos.

    Example:
        >>> ultimo = UltimoPasoResumen(
        ...     vehicle_id="69379",
        ...     label="1203",
        ...     detectado_en=datetime.now(timezone.utc)
        ... )
    """
    vehicle_id: str
    label: str | None = None
    detectado_en: datetime


class RutaConUltimoPaso(BaseModel):
    """
    Representa una ruta que pasa por una estación, con el último paso
    registrado en esa combinación.

    Se usa dentro de `EstadoEstacion` para mostrar, para cada ruta que
    sirve a una estación, el último paso de un vehículo.

    Attributes:
        route_id: Identificador de la ruta en el GTFS.
        nombre_corto: Número de la ruta (ej. "3").
        nombre_largo: Descripción extendida de la ruta (ej. "L03d03-1 tenayuca - la raza").
        color: Código de color en formato hexadecimal (ej. "#7A9A01").
        ultimo_paso: Último paso registrado para esta estación y ruta. puede ser None.

    Example:
        >>> ruta = RutaConUltimoPaso(
        ...     route_id="19429",
        ...     nombre_corto="3",
        ...     color="#7A9A01",
        ...     ultimo_paso=ultimo_paso
        ... )
    """
    route_id: str
    nombre_corto: str | None = None
    nombre_largo: str | None = None
    color: str | None = None
    ultimo_paso: UltimoPasoResumen | None = None


class EstadoEstacion(BaseModel):
    """
    Estado completo de una estación: su nombre y todas las rutas que
    pasan por ella, cada una con su último paso.

    Esta es la respuesta del endpoint GET /estaciones/{stop_id}/estado.
    Combina información estática (nombre de la estación, rutas) con información.

    Attributes:
        stop_id: Identificador de la estación.
        nombre: Nombre de la estación.
        rutas: Lista de todas las rutas que pasan por la estación,
            cada una con su último paso.

    Example:
        >>> estado = EstadoEstacion(
        ...     stop_id="fa078a",
        ...     nombre="Insurgentes",
        ...     rutas=[ruta1, ruta2]
        ... )
        >>> #Se serializa automáticamente a JSON.
    """
    stop_id: str
    nombre: str
    rutas: list[RutaConUltimoPaso]