"""
Service: pasos registrados.

Capa intermedia entre el controller y el repository. Hoy delega
directamente, pero es el lugar correcto para agregar logica de
negocio futura como:
  - Calcular tiempo transcurrido desde el ultimo paso
  - Estimar frecuencia de paso promedio
  - Alertas si una ruta lleva demasiado tiempo sin pasar
"""

import asyncpg

from app.entities.paso import PasoRegistrado
from app.repositories.pasos_repository import get_ultimo_paso, get_ultimos_pasos


async def obtener_ultimo_paso(
    conn: asyncpg.Connection, estacion_id: str, route_id: str
) -> PasoRegistrado | None:
    return await get_ultimo_paso(conn, estacion_id, route_id)


async def obtener_ultimos_pasos(
    conn: asyncpg.Connection, estacion_id: str, route_id: str
) -> list[PasoRegistrado]:
    return await get_ultimos_pasos(conn, estacion_id, route_id)