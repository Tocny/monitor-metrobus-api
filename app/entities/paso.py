"""Entidad PasoRegistrado."""

from datetime import datetime

from pydantic import BaseModel


class PasoRegistrado(BaseModel):
    id: int | None = None  # None antes de insertar en BD
    estacion_id: str
    route_id: str
    vehicle_id: str
    label: str | None = None
    detectado_en: datetime