"""
Presentation: Pydantic schemas for the FastAPI API layer.
"""
from pydantic import BaseModel


class SerZoneResponse(BaseModel):
    street_name: str
    zone_type: str
    spot_count: int
    distance_meters: int
    latitude: float
    longitude: float


class ConfigResponse(BaseModel):
    osm_tile_url: str | None


class SerZoneMapItem(BaseModel):
    street_name: str
    zone_type: str
    colour: str
    spot_count: int
    lat: float
    lng: float


class ListSerZonesResponse(BaseModel):
    city: str
    zones: list[SerZoneMapItem]
