"""
Service: mapa.

Capa intermedia entre el controller y los repositories. Hoy delega
directamente, pero es el lugar correcto para agregar logica futura
como:
  - Filtrar vehiculos inactivos (sin actualizacion reciente)
  - Enriquecer features con datos adicionales
  - Cachear el GeoJSON de rutas (cambia muy poco)
"""

import asyncpg

from app.entities.estacion import Estacion
from app.entities.ruta import Ruta
from app.entities.shape import ShapePunto
from app.entities.vehiculo import VehiculoActual
from app.repositories.estaciones_repository import get_estacion_cercana
from app.repositories.rutas_repository import get_todas_las_rutas
from app.repositories.shapes_repository import get_todos_los_puntos
from app.repositories.vehiculos_repository import get_todos_vehiculos


async def obtener_estaciones_para_mapa(
    conn: asyncpg.Connection,
) -> list[Estacion]:
    filas = await conn.fetch("SELECT stop_id, nombre, lat, lon FROM estaciones")
    return [Estacion(**dict(f)) for f in filas]


async def obtener_vehiculos_para_mapa(
    conn: asyncpg.Connection,
) -> list[VehiculoActual]:
    return await get_todos_vehiculos(conn)


async def obtener_rutas_para_mapa(
    conn: asyncpg.Connection,
) -> tuple[list[Ruta], dict[str, list[ShapePunto]]]:
    """
    Devuelve rutas y shapes juntos para que el controller construya
    el GeoJSON en una sola pasada.
    """
    rutas = await get_todas_las_rutas(conn)
    shapes = await get_todos_los_puntos(conn)
    return rutas, shapes