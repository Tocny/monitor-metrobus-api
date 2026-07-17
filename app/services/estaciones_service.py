"""
Service: estaciones.

Capa intermedia entre el controller y el repository. Hoy delega
directamente, pero es el lugar correcto para agregar logica de
negocio futura como:
  - Calcular "hace X minutos" desde el ultimo paso
  - Filtrar rutas sin actividad reciente
  - Combinar con otras fuentes de datos
"""

import asyncpg

from app.entities.estacion import Estacion, EstadoEstacion
from app.repositories.estaciones_repository import (
    get_estacion_cercana,
    get_estado_estacion,
)


async def obtener_estacion_cercana(
    conn: asyncpg.Connection, lat: float, lon: float
) -> Estacion | None:
    return await get_estacion_cercana(conn, lat, lon)


async def obtener_estado_estacion(
    conn: asyncpg.Connection, stop_id: str
) -> EstadoEstacion | None:
    return await get_estado_estacion(conn, stop_id)