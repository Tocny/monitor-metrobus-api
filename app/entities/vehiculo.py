"""Entidades de vehiculo."""

from datetime import datetime

from pydantic import BaseModel


class Vehiculo(BaseModel):
    """Vehiculo tal como viene del feed GTFS-RT (capa de servicio externo)."""
    vehicle_id: str
    label: str | None = None
    route_id: str | None = None
    lat: float
    lon: float
    velocidad: float | None = None
    timestamp: int


class VehiculoActual(BaseModel):
    """Vehiculo tal como esta guardado en la BD (ultima posicion conocida)."""
    vehicle_id: str
    label: str | None = None
    route_id: str | None = None
    lat: float
    lon: float
    velocidad: float | None = None
    feed_timestamp: int
    estacion_actual_id: str | None = None
    actualizado_en: datetime | None = None