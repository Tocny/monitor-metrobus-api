"""Entidad Ruta."""

from pydantic import BaseModel


class Ruta(BaseModel):
    route_id: str
    nombre_corto: str | None = None
    nombre_largo: str | None = None
    color: str | None = None
    agencia: str | None = None