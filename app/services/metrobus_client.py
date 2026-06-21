"""
Cliente autenticado de la API de Metrobus (SONDA).

Esas URLs caducan 10 minutos despues de generadas (segun el manual),
asi que hay que volver a llamar partnerValidation periodicamente para
refrescarlas.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from google.transit import gtfs_realtime_pb2

from app.core.config import Settings, get_settings

TIMEOUT_SEGUNDOS = 15.0

# El manual indica 10 minutos de vigencia para las URLs.
VIGENCIA_ASUMIDA_MINUTOS = 10
MARGEN_SEGURIDAD_SEGUNDOS = 60


class ErrorAutenticacionMetrobus(Exception):
    """La validacion fallo o la respuesta no trae los campos esperados."""


class UrlManager:
    """
    Llama a partnerValidation y cachea las URLs prefirmadas
    (urlRealTime, urlStatic) en memoria hasta que esten por expirar.
    Pensado para vivir como singleton durante toda la vida del
    proceso -- el worker de Fase 3 lo reutiliza en cada ciclo de
    polling en vez de revalidar cada 30 segundos.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._url_realtime: str | None = None
        self._url_static: str | None = None
        self._expira_en: datetime | None = None
        self._lock = asyncio.Lock()

    async def obtener_url_realtime(self) -> str:
        url_realtime, _ = await self._obtener_urls()
        return url_realtime

    async def obtener_url_static(self) -> str:
        """
        Bonus: la validacion tambien entrega la URL del GTFS estatico
        (.zip), que SONDA actualiza diariamente a medianoche. Util si
        mas adelante se quiere automatizar la recarga de
        scripts/cargar_gtfs_estatico.py en vez de subir el zip a mano.
        """
        _, url_static = await self._obtener_urls()
        return url_static

    def invalidar(self) -> None:
        """Fuerza una nueva validacion en la siguiente solicitud (ej. tras un 403 de S3)."""
        self._url_realtime = None
        self._url_static = None
        self._expira_en = None

    async def _obtener_urls(self) -> tuple[str, str]:
        async with self._lock:
            if self._url_realtime is None or self._esta_por_expirar():
                await self._validar()
            return self._url_realtime, self._url_static  # type: ignore[return-value]

    def _esta_por_expirar(self) -> bool:
        if self._expira_en is None:
            return True
        limite = self._expira_en - timedelta(seconds=MARGEN_SEGURIDAD_SEGUNDOS)
        return datetime.now(timezone.utc) >= limite

    async def _validar(self) -> None:
        s = self._settings
        if not s.metrobus_api_login_url:
            raise ErrorAutenticacionMetrobus("METROBUS_API_LOGIN_URL no esta configurado en .env.")

        payload = {"usuario": s.metrobus_api_usuario, "senha": s.metrobus_api_senha}

        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            try:
                resp = await client.post(s.metrobus_api_login_url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ErrorAutenticacionMetrobus(
                    f"partnerValidation rechazo la solicitud ({e.response.status_code}). "
                    f"Revisa usuario/contrasena en .env. Respuesta: {e.response.text[:300]}"
                ) from e
            except httpx.RequestError as e:
                raise ErrorAutenticacionMetrobus(f"No se pudo contactar partnerValidation: {e}") from e

        try:
            data = resp.json()
        except ValueError as e:
            raise ErrorAutenticacionMetrobus(
                f"partnerValidation no devolvio JSON valido: {resp.text[:300]}"
            ) from e

        try:
            self._url_realtime = data["urlRealTime"]
            self._url_static = data["urlStatic"]
        except KeyError as e:
            raise ErrorAutenticacionMetrobus(
                f"La respuesta de partnerValidation no trae el campo {e}. "
                f"Campos recibidos: {list(data.keys())}"
            ) from e

        self._expira_en = (
            datetime.now(timezone.utc)
            + timedelta(minutes=VIGENCIA_ASUMIDA_MINUTOS)
            - timedelta(seconds=MARGEN_SEGURIDAD_SEGUNDOS)
        )


class FeedClient:
    """Descarga y decodifica el feed GTFS-RT desde la URL prefirmada vigente."""

    def __init__(self, url_manager: UrlManager):
        self._url_manager = url_manager

    async def descargar_feed_bytes(self) -> bytes:
        url_realtime = await self._url_manager.obtener_url_realtime()
        resp = await self._descargar(url_realtime)

        if resp.status_code >= 400:
            # La URL prefirmada pudo haber caducado justo en el filo
            # (S3 normalmente responde 403 con un error tipo
            # "RequestExpired" en estos casos, a veces 400). Forzamos
            # una nueva validacion y reintentamos UNA vez.
            self._url_manager.invalidar()
            url_realtime = await self._url_manager.obtener_url_realtime()
            resp = await self._descargar(url_realtime)

        resp.raise_for_status()
        return resp.content

    @staticmethod
    async def _descargar(url: str) -> httpx.Response:
        # Las URLs prefirmadas de S3 NO necesitan ningun header de
        # autenticacion -- la firma ya viene embebida en la query string.
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            return await client.get(url)

    @staticmethod
    def decodificar_feed(contenido: bytes) -> gtfs_realtime_pb2.FeedMessage:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(contenido)
        return feed

    @staticmethod
    def extraer_vehiculos(feed: gtfs_realtime_pb2.FeedMessage) -> list[dict]:
        """
        Convierte las entidades 'vehicle' del feed a una lista de dicts
        simples, listos para usarse en el worker de Fase 3 o en
        cualquier endpoint. Usa vehicle.vehicle.id (estable) como
        identificador, no entity.id (confirmamos por diagnostico que
        este ultimo se regenera entre lecturas).
        """
        vehiculos = []
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            v = entity.vehicle
            vehiculos.append(
                {
                    "vehicle_id": v.vehicle.id if v.vehicle.HasField("id") else entity.id,
                    "label": v.vehicle.label if v.vehicle.HasField("label") else None,
                    "route_id": v.trip.route_id or None,
                    "lat": v.position.latitude,
                    "lon": v.position.longitude,
                    "velocidad": v.position.speed if v.position.HasField("speed") else None,
                    "timestamp": v.timestamp,
                }
            )
        return vehiculos


# --- Instancias compartidas (singleton simple a nivel de modulo) ---
# El worker de Fase 3 y los endpoints de debug reutilizan estas mismas
# instancias para no revalidar en cada llamada.
_settings = get_settings()
url_manager = UrlManager(_settings)
feed_client = FeedClient(url_manager)


async def obtener_vehiculos_actuales() -> list[dict]:
    """Atajo: valida (si hace falta) + descarga + decodifica + extrae vehiculos."""
    contenido = await feed_client.descargar_feed_bytes()
    feed = feed_client.decodificar_feed(contenido)
    return feed_client.extraer_vehiculos(feed)


async def obtener_url_gtfs_estatico() -> str:
    """Atajo para obtener la URL vigente del GTFS estatico (.zip)."""
    return await url_manager.obtener_url_static()
