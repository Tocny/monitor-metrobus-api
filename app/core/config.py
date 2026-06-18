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

    # --- Mapbox ---
    mapbox_token: str = Field(default="", repr=False)

    # --- Base de datos (PostgreSQL + PostGIS) ---
    database_url: str = Field(
        default="postgresql+asyncpg://metrobus:metrobus@db:5432/metrobus",
        description="Cadena de conexion async a PostgreSQL",
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
