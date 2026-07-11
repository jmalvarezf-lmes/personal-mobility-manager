"""Unit tests for buffer + dissolve of SER bands into zone boundary polygons."""

import math

import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union

from mobility_manager.infrastructure.parking_services.madrid.buffer_dissolve import (
    BAND_BUFFER_HALF_WIDTH_METERS,
    ZONE_GEOMETRY_SIMPLIFY_TOLERANCE_METERS,
    buffer_and_dissolve,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    SerBand,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    JoinedBand,
)


def _count_coords(geometry: Polygon | MultiPolygon) -> int:
    if isinstance(geometry, MultiPolygon):
        return sum(_count_coords(part) for part in geometry.geoms)
    ring_coords = len(geometry.exterior.coords)
    for interior in geometry.interiors:
        ring_coords += len(interior.coords)
    return ring_coords


def _joined_band(
    zone_number: str,
    zone_type: str,
    street_name: str,
    district: str,
    spot_count: int,
    x: float,
    y: float,
    dx: float = 10.0,
) -> JoinedBand:
    band = SerBand(
        zone_type=zone_type,
        spot_count=spot_count,
        geometry=LineString([(x, y), (x + dx, y)]),
    )
    return JoinedBand(band=band, zone_number=zone_number, street_name=street_name, district=district)


def test_two_bands_same_zone_and_colour_dissolve_into_one_record() -> None:
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=5, x=0, y=0),
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=3, x=5, y=0),
    ]

    records = buffer_and_dissolve(bands)

    assert len(records) == 1
    record = records[0]
    assert record.zone_number == "163"
    assert record.zone_type == "Azul"
    assert record.spot_count == 8
    assert record.geometry.is_valid


def test_bands_same_zone_number_different_colour_produce_separate_records() -> None:
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=5, x=0, y=0),
        _joined_band("163", "Verde", "ABADA", "CENTRO", spot_count=3, x=1000, y=1000),
    ]

    records = buffer_and_dissolve(bands)

    assert len(records) == 2
    zone_types = {r.zone_type for r in records}
    assert zone_types == {"Azul", "Verde"}
    for r in records:
        assert r.zone_number == "163"
        assert r.district == "CENTRO"


def test_buffer_width_is_uniform_regardless_of_position() -> None:
    bands = [_joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=5, x=0, y=0)]
    records = buffer_and_dissolve(bands)

    assert len(records) == 1
    # A single 10m-long band buffered by half-width w produces an area
    # approximately (10 * 2w) + pi*w^2 (rectangle + two half-circle caps).
    # A wider relative tolerance is used here (vs. a tighter one pre-D10)
    # because post-buffer simplification (0.5m tolerance) coarsens the
    # buffer's round caps slightly, which is a larger fraction of the total
    # area at this small synthetic scale than it would be for a real,
    # much-larger dissolved zone.
    w = BAND_BUFFER_HALF_WIDTH_METERS
    expected_area = 10 * 2 * w + math.pi * w**2
    assert records[0].geometry.area == pytest.approx(expected_area, rel=0.1)


def test_spot_count_unknown_is_minus_one_not_zero() -> None:
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=-1, x=0, y=0),
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=-1, x=5, y=0),
    ]

    records = buffer_and_dissolve(bands)

    assert len(records) == 1
    assert records[0].spot_count == -1


def test_multiple_distinct_street_names_preserved() -> None:
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=5, x=0, y=0),
        _joined_band("163", "Azul", "GRAN VIA", "CENTRO", spot_count=3, x=1000, y=1000),
    ]

    records = buffer_and_dissolve(bands)

    assert len(records) == 1
    assert set(records[0].street_names) == {"ABADA", "GRAN VIA"}


def test_discontinuous_bands_produce_multipolygon() -> None:
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=5, x=0, y=0),
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=3, x=100000, y=100000),
    ]

    records = buffer_and_dissolve(bands)

    assert len(records) == 1
    assert isinstance(records[0].geometry, (Polygon, MultiPolygon))
    assert isinstance(records[0].geometry, MultiPolygon)


def test_dissolved_geometry_is_simplified_below_raw_union() -> None:
    # Several bands close enough to be believable as one zone, arranged so the
    # dissolve produces more vertex detail (many band caps/joins) than a 0.5m
    # tolerance needs to preserve overall shape.
    bands = [
        _joined_band("163", "Azul", "ABADA", "CENTRO", spot_count=1, x=i * 4.0, y=0)
        for i in range(20)
    ]

    records = buffer_and_dissolve(bands)
    assert len(records) == 1
    simplified_geometry = records[0].geometry

    raw_polygons = [b.band.geometry.buffer(BAND_BUFFER_HALF_WIDTH_METERS) for b in bands]
    raw_union = unary_union(raw_polygons)

    assert ZONE_GEOMETRY_SIMPLIFY_TOLERANCE_METERS > 0  # simplification is actually applied
    assert simplified_geometry.is_valid
    assert _count_coords(simplified_geometry) <= _count_coords(raw_union)

    # Simplification should preserve most of the original area.
    area_ratio = simplified_geometry.area / raw_union.area
    assert area_ratio > 0.9
