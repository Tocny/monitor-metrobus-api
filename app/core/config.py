"""
Configuracion centralizada de la aplicacion.

Todos los valores sensibles (credenciales, tokens) se leen desde
variables de entorno -- NUNCA se hardcodean aqui ni en ningun otro
archivo del repo. En desarrollo local se proveen via un archivo .env
(que esta en .gitignore); en produccion/Docker se inyectan como
variables de entorno reales o secrets.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Metadatos de la app ---
    app_name: str = "Monitor Metrobus API"
    environment: str = Field(default="development")  # development | production
    debug: bool = Field(default=True)

    # --- API oficial de Metrobus (datos en tiempo real) ---
    metrobus_api_login_url: str = Field(
        default="",
        description="URL del endpoint POST de login que devuelve el token",
    )
    metrobus_api_usuario: str = Field(default="", repr=False)
    metrobus_api_senha: str = Field(default="", repr=False)
    metrobus_feed_url: str = Field(
        default="",
        description="URL del feed GTFS-RT (puede requerir el token de login)",
    )

    # --- Como interpretar la respuesta del login ---
    # AJUSTA ESTO segun la respuesta real de tu API. Por ejemplo, si tu
    # API responde {"access_token": "...", "expira_en": 3600}, pondrias
    # metrobus_token_field="access_token" y
    # metrobus_token_expiry_field="expira_en".
    metrobus_token_field: str = Field(
        default="token",
        description="Nombre del campo en la respuesta JSON del login que trae el token",
    )
    metrobus_token_expiry_field: str = Field(
        default="",
        description=(
            "Nombre del campo que trae la duracion del token en segundos "
            "(dejar vacio si la API no lo informa -- se usara un TTL asumido)"
        ),
    )
    metrobus_token_assumed_ttl_seconds: int = Field(
        default=1800,
        description="TTL asumido del token si la API no informa expiracion (30 min por defecto)",
    )

    # --- Como mandar el token de vuelta al pedir el feed ---
    # AJUSTA ESTO segun lo que pida tu API: la mayoria usa un header
    # "Authorization: Bearer <token>" (la opcion por defecto), pero
    # algunas piden el token como query param (?token=...) o un header
    # con otro nombre.
    metrobus_auth_location: str = Field(
        default="header",
        description="Donde va el token al pedir el feed: 'header' o 'query_param'",
    )
    metrobus_auth_header_name: str = Field(default="Authorization")
    metrobus_auth_scheme: str = Field(
        default="Bearer",
        description="Prefijo del header, ej. 'Bearer'. Dejar vacio si la API no usa prefijo.",
    )
    metrobus_auth_query_param_name: str = Field(default="token")

    # --- Mapbox ---
    mapbox_token: str = Field(default="", repr=False)

    # --- Base de datos (PostgreSQL + PostGIS, sin ORM -- via asyncpg) ---
    # En desarrollo apunta al contenedor local "db" del docker-compose.
    # En produccion, cambia esto por tu connection string de Supabase
    # (Project Settings > Database > Connection string > URI), algo como:
    #   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
    database_url: str = Field(
        default="postgresql://metrobus:metrobus@db:5432/metrobus",
        description="Cadena de conexion a PostgreSQL (formato estandar, sin sufijo de driver)",
    )

    # --- Parametros del worker de polling ---
    polling_interval_seconds: int = Field(
        default=30,
        description="Cada cuanto se consulta el feed GTFS-RT (el proveedor actualiza cada 30s)",
    )
    station_radius_meters: float = Field(
        default=70.0,
        description="Radio para considerar que un vehiculo 'esta en' una estacion",
    )


@lru_cache
def get_settings() -> Settings:
    """Cachea la instancia de configuracion para no releer el .env en cada request."""
    return Settings()
