"""
Entidades relacionadas con frecuencias de paso.

Este módulo define el objeto de transferencia de datos que representa
la frecuencia promedio de una ruta en una estación específica.

Estas entidades son utilizadas por:
    - Los repositorios.
    - Los servicios.
"""

from datetime import datetime
from pydantic import BaseModel


class FrecuenciaRutaEstacion(BaseModel):
    """
    Representa la frecuencia promedio de paso de una ruta en una estación.

    Almacena el intervalo medio (en minutos) entre vehículos de una ruta
    que pasan por una estación determinada. El valor se calcula a partir
    de los pasos registrados en una ventana de tiempo (por ejemplo, las
    últimas 24 horas) y puede ser nulo si no hay suficientes datos.

    Esta entidad se utiliza para responder a consultas sobre la regularidad
    del servicio y para estimar tiempos de espera.

    Attributes:
        stop_id: Identificador de la estación (stop_id). 
        route_id: Identificador de la ruta (route_id). 
        intervalo_minutos: Intervalo promedio entre vehículos, en minutos.
        calculado_en: Marca de tiempo con zona horaria (UTC) que indica
            cuándo fue calculado

    Example:
        >>> from datetime import datetime, timezone
        >>> frecuencia = FrecuenciaRutaEstacion(
        ...     stop_id="fa078a",
        ...     route_id="insurgentes",
        ...     intervalo_minutos=7.5,
        ...     calculado_en=datetime.now(timezone.utc)
        ... )
        >>> print(frecuencia.model_dump_json())
    """
    stop_id: str
    route_id: str
    intervalo_minutos: float | None = None  # None si hay menos de 2 pasos en la ventana
    calculado_en: datetime