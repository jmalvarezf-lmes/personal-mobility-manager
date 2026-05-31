"""
Presentation: Pydantic schemas for the FastAPI API layer.
"""
from pydantic import BaseModel


class SerZoneResponse(BaseModel):
    street_name: str
    zone_code: str
    zone_label: str
    distance_meters: int
    latitude: float
    longitude: float
