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

    # --- API oficial de Metrobus (SONDA) ---
    # Segun el manual de SONDA, este endpoint ("partnerValidation") NO
    # devuelve un token Bearer -- devuelve directamente dos URLs
    # prefirmadas de S3 (urlRealTime, urlStatic) listas para descargar
    # con un GET simple, sin headers de autenticacion adicionales.
    # Caducan 10 minutos despues de generadas, asi que hay que volver
    # a llamar este endpoint periodicamente para refrescarlas (ver
    # app/services/metrobus_client.py).
    metrobus_api_login_url: str = Field(
        default="",
        description="Endpoint de validacion que devuelve las URLs prefirmadas del feed (METROBUS_API_LOGIN_URL en .env)",
    )
    metrobus_api_usuario: str = Field(default="", repr=False)
    metrobus_api_senha: str = Field(default="", repr=False)

    # --- Mapbox ---
    mapbox_token: str = Field(default="", repr=False)

    # --- Base de datos (PostgreSQL + PostGIS, sin ORM -- via asyncpg) ---
    # En desarrollo apunta al contenedor local "db" del docker-compose.
    # En produccion, cambia esto por tu connection string de Supabase
    # (Project Settings > Database > Connection string > URI), algo como:
    #   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
    database_url: str = Field(
        default="",
        description="Cadena de conexion a PostgreSQL (DATABASE_URL en .env, formato estandar sin sufijo de driver)",
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
