"""Entidades de estacion."""

from datetime import datetime

from pydantic import BaseModel


class Estacion(BaseModel):
    stop_id: str
    nombre: str
    lat: float
    lon: float


# --- para GET /estaciones/{stop_id}/estado ---

class UltimoPasoResumen(BaseModel):
    vehicle_id: str
    label: str | None = None
    detectado_en: datetime


class RutaConUltimoPaso(BaseModel):
    route_id: str
    nombre_corto: str | None = None
    nombre_largo: str | None = None
    color: str | None = None
    ultimo_paso: UltimoPasoResumen | None = None


class EstadoEstacion(BaseModel):
    stop_id: str
    nombre: str
    rutas: list[RutaConUltimoPaso]