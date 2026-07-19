"""
Service: cliente del feed externo de Metrobus.

Tiene que obtener vehículos actuales desde la API de SONDA y devolverlos 
como entidades Vehiculo.

El cliente renueva las urls cada 10 minutos antes de que expiren.

Flujo:
    1. Se llama a obtener_vehiculos_actuales().
    2. Si las URLs cacheadas no existen o están cerca de expirar,
       se autentica con partnerValidation para obtener nuevas URLs.
    3. Se descarga el feed desde la URL prefirmada.
    4. Se decodifica el feed.
    5. Se transforma cada entidad del feed en un objeto Vehiculo.

Dependencias:
    - httpx
    - gtfs-realtime-bindings
    - app.core.config 
    - app.entities.vehiculo
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from google.transit import gtfs_realtime_pb2

from app.core.config import get_settings
from app.entities.vehiculo import Vehiculo

logger = logging.getLogger(__name__)
settings = get_settings()

# Constantes de configuración
TIMEOUT_SEGUNDOS: float = 15.0
"""Timeout en segundos para las peticiones HTTP a SONDA y S3."""

VIGENCIA_MINUTOS: int = 10
"""Tiempo de vigencia de las URLs."""

MARGEN_SEGUNDOS: int = 60
"""Margen de seguridad para renovar la URL antes de que expire."""


class ErrorAutenticacionMetrobus(Exception):
    """
    Excepción lanzada cuando falla la autenticación con la API de SONDA.

    Puede deberse a:
        - Credenciales incorrectas.
        - El endpoint partnerValidation no responde.
        - La respuesta del servidor no tiene el formato esperado.
    """


# Estado del módulo (URLs cacheadas)

_url_realtime: str | None = None
"""URL prefirmada de S3 para el feed en tiempo real."""

_url_static: str | None = None
"""URL prefirmada de S3 para el GTFS estático."""

_expira_en: datetime | None = None
"""Marca de tiempo (UTC) en que expiran las URLs."""

_lock = asyncio.Lock()
"""Lock asíncrono para evitar múltiples renovaciones simultáneas de la URL."""


def _esta_por_expirar() -> bool:
    """
    Indica si la URL cacheada está próxima a expirar.

    Se considera que está por expirar si la hora actual es mayor o igual
    a (expiración - MARGEN_SEGUNDOS). Esto evita que se use una URL
    que caduque mientras descargamos el feed.

    Returns:
        True si no hay URL o si está por expirar, False eoc.
    """
    if _expira_en is None:
        return True
    return datetime.now(timezone.utc) >= _expira_en - timedelta(seconds=MARGEN_SEGUNDOS)


async def _validar() -> None:
    """
    Autentica contra el endpoint partnerValidation de SONDA y actualiza
    las URLs prefirmadas cacheadas.

    Realiza una petición POST con las credenciales
    Si la autenticación es exitosa, guarda las URLs de realtime y estático,
    y registra la hora de expiración (10 minutos después).

    Raises:
        ErrorAutenticacionMetrobus: Si falla la autenticación, si el
            endpoint no responde, o si la respuesta no tiene el formato esperado.
    """
    global _url_realtime, _url_static, _expira_en

    s = settings
    if not s.metrobus_api_login_url:
        raise ErrorAutenticacionMetrobus(
            "METROBUS_API_LOGIN_URL no configurado en .env."
        )

    payload = {"usuario": s.metrobus_api_usuario, "senha": s.metrobus_api_senha}

    async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
        try:
            resp = await client.post(s.metrobus_api_login_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ErrorAutenticacionMetrobus(
                f"partnerValidation rechazó la solicitud ({e.response.status_code}): "
                f"{e.response.text[:300]}"
            ) from e
        except httpx.RequestError as e:
            raise ErrorAutenticacionMetrobus(
                f"No se pudo contactar partnerValidation: {e}"
            ) from e

    try:
        data = resp.json()
        _url_realtime = data["urlRealTime"]
        _url_static = data["urlStatic"]
    except (ValueError, KeyError) as e:
        raise ErrorAutenticacionMetrobus(
            f"Respuesta inesperada de partnerValidation: {e}. "
            f"Campos recibidos: {list(data.keys()) if isinstance(data, dict) else 'no es JSON'}"
        ) from e

    _expira_en = datetime.now(timezone.utc) + timedelta(minutes=VIGENCIA_MINUTOS)
    logger.debug("URLs prefirmadas renovadas. Expiran en %d min.", VIGENCIA_MINUTOS)


async def _obtener_url_realtime() -> str:
    """
    Retorna la URL prefirmada vigente para el feed en tiempo real.

    Si la URL cacheada no existe o está por expirar, se autentica
    automáticamente para obtener una nueva.
    Usamos un un lock para evitar multiples validaciones concurrentes.

    Returns:
        URL prefirmada de S3 para el feed en tiempo real.

    Raises:
        ErrorAutenticacionMetrobus: Si falla la autenticación.
    """
    global _url_realtime
    async with _lock:
        if _url_realtime is None or _esta_por_expirar():
            await _validar()
    return _url_realtime  # type: ignore[return-value]


# API service

async def obtener_vehiculos_actuales() -> list[Vehiculo]:
    """
    Obtiene la lista de vehículos activos desde el feed GTFS-RT.

    Este es el punto de entrada del módulo. Realiza:
        1. Obtiene una URL prefirmada válida (renovándola si es necesario).
        2. Descarga el feed desde S3.
        3. Si la URL expiró justo en el límite, la renueva y reintenta.
        4. Decodifica el feed con Protocol Buffers.
        5. Transforma cada entidad vehicle en un objeto Vehiculo.

    El feed se actualiza cada 30 segundos.

    Returns:
        Lista de objetos Vehiculo con los datos de todos los autobuses
        activos en el momento de la consulta.

    Raises:
        ErrorAutenticacionMetrobus: Si falla la autenticación.
        httpx.HTTPError: Si falla la descarga del feed (después del reintento).

    Example:
        >>> vehiculos = await obtener_vehiculos_actuales()
        >>> len(vehiculos)
        829
        >>> vehiculos[0]
        Vehiculo(vehicle_id='69379', label='1203', lat=19.467..., ...)
    """
    url = await _obtener_url_realtime()

    # Primera tentativa de descarga
    async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
        resp = await client.get(url)

    # Si el servidor responde con error (p.ej. 403 por URL expirada),
    # forzamos la renovación y reintentamos una vez.
    if resp.status_code >= 400:
        async with _lock:
            global _url_realtime, _expira_en
            _url_realtime = None
            _expira_en = None
        url = await _obtener_url_realtime()
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(url)

    resp.raise_for_status()

    # Decodificación del feed
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)

    vehiculos: list[Vehiculo] = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle

        # Extraer vehicle_id: se prefiere vehicle.vehicle.id,
        # pero si no está disponible se usa entity.id.
        vehicle_id = v.vehicle.id if v.vehicle.HasField("id") else entity.id

        vehiculos.append(Vehiculo(
            vehicle_id=vehicle_id,
            label=v.vehicle.label if v.vehicle.HasField("label") else None,
            route_id=v.trip.route_id or None,
            lat=v.position.latitude,
            lon=v.position.longitude,
            velocidad=v.position.speed if v.position.HasField("speed") else None,
            timestamp=v.timestamp,
        ))

    return vehiculos


async def obtener_url_gtfs_estatico() -> str:
    """
    Retorna la URL prefirmada vigente para el GTFS estático (.zip).

    Esta función es análoga a _obtener_url_realtime, pero para el
    archivo ZIP de datos estáticos. Se usa en el script de carga
    o para descargar el GTFS actualizado.

    Returns:
        URL prefirmada de S3 para el archivo GTFS_ESTATICO.zip.

    Raises:
        ErrorAutenticacionMetrobus: Si falla la autenticación.
    """
    async with _lock:
        if _url_static is None or _esta_por_expirar():
            await _validar()
    return _url_static 