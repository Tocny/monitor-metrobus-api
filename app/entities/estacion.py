"""Entidad Estacion."""

from pydantic import BaseModel


class Estacion(BaseModel):
    stop_id: str
    nombre: str
    lat: float
    lon: float