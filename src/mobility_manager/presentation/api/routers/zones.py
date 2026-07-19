"""
Presentation: Zones API router.

Exposes GET /parking/ser-zones to return all stored SER zones (and their
presentation-only frontiers) for a city, suitable for bulk map rendering.
Street names are deliberately excluded from this response — see design.md
D9 of add-ser-zone-boundaries.

Also exposes GET /parking/ser-zone-options, a lightweight sibling that
returns only zone_number + neighbourhood pairs (no geometry) for a city.
It exists because the SER parking exemption picker's zone <select> only
needs those two text fields per option, while /ser-zones reprojects and
returns full GeoJSON polygon geometry for every zone and frontier row —
fetching that just to populate a dropdown was slow (~5s for Madrid's ~154
zones/~66 frontiers) and made an already-known selection look unselected
until the heavy response resolved. See the fix for the two live-testing
bugs found in add-vehicle-ser-parking-exemption.

`city` is validated against the live `cities` table (see city-registry
spec.md) rather than a hardcoded set, and the /ser-zones response is
fetched via city-scoped repository queries
(list_zones_for_city/list_zone_areas_for_city) so a second city's data
never leaks into a single-city response — see design.md D6/D7 of
add-vehicle-ser-parking-exemption.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from mobility_manager.domain.ports.city_repository import CityRepository
from mobility_manager.infrastructure.parking_services.madrid.zone_type import (
    MadridZoneType,
)
from mobility_manager.presentation.api.geojson import geometry_to_wgs84_geojson
from mobility_manager.presentation.api.schemas import (
    FrontierMapItem,
    ListSerZonesResponse,
    ListZoneOptionsResponse,
    SerZoneMapItem,
    ZoneOptionItem,
)

router = APIRouter(prefix="/parking", tags=["parking"])


def _resolve_colour(city: str, zone_type_str: str) -> str:
    if city == "madrid":
        zt = MadridZoneType.from_raw(zone_type_str)
        return zt.colour if zt is not None else "#6B7280"
    return "#6B7280"


def _require_known_city(city: str, city_repo: CityRepository) -> None:
    """Raise 404 unless `city` matches a row in the live `cities` table.

    Shared by both endpoints in this router so the city-validation rule
    (live table, not a hardcoded set — see design.md D6 of
    add-vehicle-ser-parking-exemption) stays in one place.
    """
    known_city_codes = {c.code for c in city_repo.list_all()}
    if city not in known_city_codes:
        raise HTTPException(status_code=404, detail=f"City '{city}' is not supported")


@router.get("/ser-zones", response_model=ListSerZonesResponse)
def list_ser_zones(
    request: Request,
    city: str = Query(..., description="City code (e.g. 'madrid')"),
) -> ListSerZonesResponse:
    """Return all SER zones (and frontiers) for the given city, with geometry reprojected to WGS84 GeoJSON."""
    _require_known_city(city, request.app.state.city_repo)

    repo = request.app.state.ser_zone_repo
    zones = repo.list_zones_for_city(city)
    zone_areas = repo.list_zone_areas_for_city(city)

    return ListSerZonesResponse(
        city=city,
        zones=[
            SerZoneMapItem(
                zone_number=z.zone_number,
                zone_type=z.zone_type,
                colour=_resolve_colour(city, z.zone_type),
                district=z.district,
                spot_count=z.spot_count,
                geometry=geometry_to_wgs84_geojson(z.geometry),
            )
            for z in zones
        ],
        frontiers=[
            FrontierMapItem(
                zone_number=za.zone_number,
                neighbourhood=za.neighbourhood,
                geometry=geometry_to_wgs84_geojson(za.geometry),
            )
            for za in zone_areas
        ],
    )


@router.get("/ser-zone-options", response_model=ListZoneOptionsResponse)
def list_ser_zone_options(
    request: Request,
    city: str = Query(..., description="City code (e.g. 'madrid')"),
    sort: Literal["asc", "desc"] = Query(
        "asc", description="Sort direction for the returned options by neighbourhood name."
    ),
) -> ListZoneOptionsResponse:
    """
    Return zone_number + neighbourhood pairs for the given city, with no
    geometry reprojection — the lightweight sibling of GET /ser-zones for
    callers (e.g. the SER parking exemption picker) that only need to label
    a zone <select>, not render polygons.

    `sort` ("asc", default, or "desc") controls the alphabetical ordering of
    the returned options by `neighbourhood` — the display label shown in the
    <option>, not `zone_number` (which is how the repository orders rows).
    Sorting happens here, in Python, over the already-fetched list: it is a
    presentation-only concern specific to this endpoint's dropdown, and the
    dataset is small (~66 rows for Madrid), so no SQL/repository-level
    ordering was added to `list_zone_areas_for_city` (also used by
    /ser-zones, which has no such ordering need).
    """
    _require_known_city(city, request.app.state.city_repo)

    repo = request.app.state.ser_zone_repo
    zone_areas = repo.list_zone_areas_for_city(city)
    zone_areas = sorted(zone_areas, key=lambda za: za.neighbourhood, reverse=(sort == "desc"))

    return ListZoneOptionsResponse(
        city=city,
        options=[
            ZoneOptionItem(zone_number=za.zone_number, neighbourhood=za.neighbourhood) for za in zone_areas
        ],
    )
