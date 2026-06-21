"""
Cliente autenticado contra la API real de Metrobus.

Reemplaza el link presignado de S3 (temporal, ~12h) que usabamos en
los scripts de prueba, por un flujo real: login con usuario/contrasena
-> token -> usar el token para pedir el feed -> si el token expira
(401/403), renovar automaticamente y reintentar una vez.

NOTA IMPORTANTE: los nombres de campo y el mecanismo de autenticacion
estan parametrizados en Settings porque no conocemos el formato exacto
de tu API. Si algo no funciona al probarlo, lo primero que hay que
revisar es:
  1. metrobus_token_field -- el campo del JSON de login que trae el token
  2. metrobus_auth_location / metrobus_auth_header_name / metrobus_auth_scheme
     -- como tu API espera recibir el token de vuelta
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from google.transit import gtfs_realtime_pb2

from app.core.config import Settings, get_settings

TIMEOUT_SEGUNDOS = 15.0
# Margen de seguridad: renueva el token un poco antes de que expire,
# no justo en el limite.
MARGEN_EXPIRACION_SEGUNDOS = 60


class ErrorAutenticacionMetrobus(Exception):
    """El login fallo o la respuesta no trae el token esperado."""


class TokenManager:
    """
    Maneja el ciclo de vida del token: login, cache en memoria,
    renovacion cuando expira. Pensado para vivir como singleton
    durante toda la vida del proceso (el worker de Fase 3 lo reutiliza
    en cada ciclo de polling en vez de loguearse cada 30 segundos).
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._token: str | None = None
        self._expira_en: datetime | None = None
        self._lock = asyncio.Lock()

    async def obtener_token_valido(self) -> str:
        async with self._lock:
            if self._token is None or self._esta_por_expirar():
                await self._login()
            return self._token  # type: ignore[return-value]

    def invalidar(self) -> None:
        """Fuerza un nuevo login en la siguiente solicitud (ej. tras un 401)."""
        self._token = None
        self._expira_en = None

    def _esta_por_expirar(self) -> bool:
        if self._expira_en is None:
            # La API no informo expiracion -- nos apoyamos en la
            # deteccion de 401/403 al pedir el feed para renovar.
            return False
        limite = self._expira_en - timedelta(seconds=MARGEN_EXPIRACION_SEGUNDOS)
        return datetime.now(timezone.utc) >= limite

    async def _login(self) -> None:
        s = self._settings
        if not s.metrobus_api_login_url:
            raise ErrorAutenticacionMetrobus("METROBUS_API_LOGIN_URL no esta configurado.")

        payload = {"usuario": s.metrobus_api_usuario, "senha": s.metrobus_api_senha}

        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            try:
                resp = await client.post(s.metrobus_api_login_url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ErrorAutenticacionMetrobus(
                    f"Login rechazado ({e.response.status_code}). "
                    f"Revisa usuario/contrasena en .env. Respuesta: {e.response.text[:300]}"
                ) from e
            except httpx.RequestError as e:
                raise ErrorAutenticacionMetrobus(f"No se pudo contactar el login: {e}") from e

        try:
            data = resp.json()
        except ValueError as e:
            raise ErrorAutenticacionMetrobus(
                f"El login no devolvio JSON valido: {resp.text[:300]}"
            ) from e

        token = data.get(s.metrobus_token_field)
        if not token:
            raise ErrorAutenticacionMetrobus(
                f"La respuesta del login no trae el campo '{s.metrobus_token_field}'. "
                f"Campos disponibles: {list(data.keys())}. "
                f"Ajusta METROBUS_TOKEN_FIELD en .env con el nombre correcto."
            )

        self._token = token

        if s.metrobus_token_expiry_field and s.metrobus_token_expiry_field in data:
            segundos_ttl = int(data[s.metrobus_token_expiry_field])
            self._expira_en = datetime.now(timezone.utc) + timedelta(seconds=segundos_ttl)
        else:
            # Sin info de expiracion: asumimos un TTL conservador y de
            # todas formas la renovacion-por-401 actua como respaldo.
            self._expira_en = datetime.now(timezone.utc) + timedelta(
                seconds=s.metrobus_token_assumed_ttl_seconds
            )


class FeedClient:
    """Descarga y decodifica el feed GTFS-RT usando un token valido."""

    def __init__(self, settings: Settings, token_manager: TokenManager):
        self._settings = settings
        self._token_manager = token_manager

    async def descargar_feed_bytes(self) -> bytes:
        token = await self._token_manager.obtener_token_valido()
        resp = await self._pedir_feed(token)

        if resp.status_code in (401, 403):
            # El token pudo haber expirado sin que lo supieramos
            # (API sin campo de expiracion, o token revocado). Forzamos
            # un login nuevo y reintentamos UNA vez.
            self._token_manager.invalidar()
            token = await self._token_manager.obtener_token_valido()
            resp = await self._pedir_feed(token)

        resp.raise_for_status()
        return resp.content

    async def _pedir_feed(self, token: str) -> httpx.Response:
        s = self._settings
        headers = {}
        params = {}

        if s.metrobus_auth_location == "query_param":
            params[s.metrobus_auth_query_param_name] = token
        else:
            valor_header = f"{s.metrobus_auth_scheme} {token}".strip()
            headers[s.metrobus_auth_header_name] = valor_header

        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            return await client.get(s.metrobus_feed_url, headers=headers, params=params)

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
# instancias para no loguearse de nuevo en cada llamada.
_settings = get_settings()
token_manager = TokenManager(_settings)
feed_client = FeedClient(_settings, token_manager)


async def obtener_vehiculos_actuales() -> list[dict]:
    """Atajo: login (si hace falta) + descarga + decodifica + extrae vehiculos."""
    contenido = await feed_client.descargar_feed_bytes()
    feed = feed_client.decodificar_feed(contenido)
    return feed_client.extraer_vehiculos(feed)
