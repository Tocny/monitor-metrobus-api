"""
Service: cliente del feed externo de Metrobus (SONDA).

Responsabilidad unica: obtener vehiculos actuales desde la API de
SONDA y devolverlos como entidades Vehiculo. No sabe nada de BD ni
de logica de negocio.

La API de SONDA (partnerValidation) devuelve URLs prefirmadas de S3
directamente -- no un token Bearer. Caducan 10 minutos despues de
generadas, por lo que se renuevan automaticamente cuando estan por
expirar.
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

TIMEOUT_SEGUNDOS = 15.0
VIGENCIA_MINUTOS = 10
MARGEN_SEGUNDOS = 60


class ErrorAutenticacionMetrobus(Exception):
    pass


# ---------------------------------------------------------------------------
# Estado del modulo (URLs prefirmadas cacheadas)
# ---------------------------------------------------------------------------

_url_realtime: str | None = None
_url_static: str | None = None
_expira_en: datetime | None = None
_lock = asyncio.Lock()


def _esta_por_expirar() -> bool:
    if _expira_en is None:
        return True
    return datetime.now(timezone.utc) >= _expira_en - timedelta(seconds=MARGEN_SEGUNDOS)


async def _validar() -> None:
    global _url_realtime, _url_static, _expira_en

    s = settings
    if not s.metrobus_api_login_url:
        raise ErrorAutenticacionMetrobus("METROBUS_API_LOGIN_URL no configurado en .env.")

    payload = {"usuario": s.metrobus_api_usuario, "senha": s.metrobus_api_senha}

    async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
        try:
            resp = await client.post(s.metrobus_api_login_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ErrorAutenticacionMetrobus(
                f"partnerValidation rechazo la solicitud ({e.response.status_code}): "
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
    global _url_realtime
    async with _lock:
        if _url_realtime is None or _esta_por_expirar():
            await _validar()
    return _url_realtime  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# API publica del service
# ---------------------------------------------------------------------------

async def obtener_vehiculos_actuales() -> list[Vehiculo]:
    """
    Valida contra SONDA si hace falta, descarga el feed GTFS-RT,
    lo decodifica y devuelve la lista de vehiculos como entidades.
    Reintenta una vez si la URL prefirmada caduco en el filo.
    """
    url = await _obtener_url_realtime()

    async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
        resp = await client.get(url)

    if resp.status_code >= 400:
        # URL expirada justo en el limite -- forzar renovacion y reintentar.
        async with _lock:
            global _url_realtime, _expira_en
            _url_realtime = None
            _expira_en = None
        url = await _obtener_url_realtime()
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            resp = await client.get(url)

    resp.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)

    vehiculos = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        vehiculos.append(Vehiculo(
            vehicle_id=v.vehicle.id if v.vehicle.HasField("id") else entity.id,
            label=v.vehicle.label if v.vehicle.HasField("label") else None,
            route_id=v.trip.route_id or None,
            lat=v.position.latitude,
            lon=v.position.longitude,
            velocidad=v.position.speed if v.position.HasField("speed") else None,
            timestamp=v.timestamp,
        ))

    return vehiculos


async def obtener_url_gtfs_estatico() -> str:
    """Devuelve la URL prefirmada vigente del GTFS estatico (.zip)."""
    async with _lock:
        if _url_static is None or _esta_por_expirar():
            await _validar()
    return _url_static  # type: ignore[return-value]