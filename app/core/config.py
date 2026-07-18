"""
Configuración de la aplicación.

Todos los valores sensibles (credenciales, tokens) se leen desde
variables de entorno. En desarrollo local se proveen mediante un archivo
.env.

La configuración se carga una sola vez y se cachea con @lru_cache
para evitar leer el .env en cada request.

Uso típico:
    from app.core.config import get_settings
    settings = get_settings()
    url = settings.metrobus_api_login_url

Dependencias:
    - pydantic-settings
    - python-dotenv 
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración centralizada de la aplicación.

    Todas las variables se cargan desde el archivo .env 
    o desde las variables de entorno del sistema.

    Attributes:
        model_config: Configuración de Pydantic para cargar el .env.
        app_name: Nombre de la aplicación.
        environment: Entorno de ejecución (development/production).
        debug: Modo debug.
        metrobus_api_login_url: Endpoint de validación de SONDA
        metrobus_api_usuario: Usuario para la API de SONDA.
        metrobus_api_senha: Contraseña para la API de SONDA.
        mapbox_token: Token público de Mapbox.
        database_url: Cadena de conexión a PostgreSQL.
        polling_interval_seconds: Intervalo de actualización del feed en segundos.
        station_radius_meters: Radio para detectar que un vehículo está en una estación.

    Example:
        >>> settings = get_settings()
        >>> print(settings.app_name)
        'Monitor Metrobus API'
        >>> # Los campos sensibles no se muestran en logs
        >>> print(settings)
        app_name='Monitor Metrobus API' metrobus_api_usuario='***' ...
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Datos de la app 
    app_name: str = "Monitor Metrobus API"
    """Nombre de la aplicación (usado en logs y respuestas de la API)."""

    environment: str = Field(default="development")
    """Entorno de ejecución: "development" o "production"."""

    debug: bool = Field(default=True)
    """Modo debug: True para logs más detallados, False para logs resumidos."""

    # API del metrobus SONDA
    # Caducan 10 minutos después de generadas, así que hay que volver
    # a llamar este endpoint periódicamente para refrescarlas
    metrobus_api_login_url: str = Field(
        default="",
        description="Endpoint de validación que devuelve las URLs prefirmadas del feed (METROBUS_API_LOGIN_URL en .env)",
    )
    """URL del endpoint de autenticación de SONDA."""

    metrobus_api_usuario: str = Field(default="", repr=False)
    """Usuario para la API de SONDA."""

    metrobus_api_senha: str = Field(default="", repr=False)
    """Contraseña para la API de SONDA."""

    #  Mapbox 
    mapbox_token: str = Field(default="", repr=False)
    """
    Token público de Mapbox para el mapa.
    """

    # Base de datos (PostgreSQL + PostGIS, asyncpg) 
    database_url: str = Field(
        default="",
        description="Cadena de conexión a PostgreSQL (DATABASE_URL en .env, formato estándar sin sufijo de driver)",
    )
    """Cadena de conexión a PostgreSQL"""

    #  Parámetros del worker de polling
    polling_interval_seconds: int = Field(
        default=30,
        description="Cada cuanto se consulta el feed GTFS-RT (el proveedor actualiza cada 30s)",
    )
    """Intervalo en segundos entre consultas al feed GTFS-RT (30s)."""

    station_radius_meters: float = Field(
        default=70.0,
        description="Radio para considerar que un vehículo 'está en' una estación",
    )
    """Radio en metros para detectar que un vehículo está en una estación (default: 70m)."""


@lru_cache
def get_settings() -> Settings:
    """
    Retorna la instancia de configuración.

    Usa lru_cache para que el archivo .env se lea una vez,
    Las siguientes llamadas devuelven la misma instancia.

    Returns:
        Instancia única de Settings con todas las variables
        de configuración cargadas.

    Example:
        >>> settings = get_settings()
        >>> settings.polling_interval_seconds
        30
    """
    return Settings()