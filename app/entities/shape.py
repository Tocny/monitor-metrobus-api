"""Entidad ShapePunto."""

from pydantic import BaseModel


class ShapePunto(BaseModel):
    route_id: str
    secuencia: int
    lat: float
    lon: float