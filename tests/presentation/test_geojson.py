"""Unit tests for the UTM -> WGS84 GeoJSON reprojection helper."""

from shapely.geometry import Polygon

from mobility_manager.presentation.api.geojson import geometry_to_wgs84_geojson

# Square in EPSG:25830 near central Madrid, matching other tests' fixture.
_SQUARE = Polygon([(440280, 4474247), (440300, 4474247), (440300, 4474267), (440280, 4474267)])


def _max_decimal_places(value: float) -> int:
    text = repr(value)
    if "e" in text or "E" in text:
        # Scientific notation implies a very small magnitude; treat as
        # effectively rounded for this test's purposes.
        return 0
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def _iter_coordinates(coords: object) -> list[tuple[float, float]]:
    """Flatten a GeoJSON-style nested coordinates structure into (x, y) pairs."""
    points: list[tuple[float, float]] = []
    if not coords:
        return points
    first = coords[0]  # type: ignore[index]
    if isinstance(first, (int, float)):
        x, y = coords[0], coords[1]  # type: ignore[index]
        points.append((x, y))
    else:
        for item in coords:  # type: ignore[union-attr]
            points.extend(_iter_coordinates(item))
    return points


def test_reprojected_geometry_is_valid_wgs84_geojson() -> None:
    geojson = geometry_to_wgs84_geojson(_SQUARE)

    assert geojson["type"] == "Polygon"
    coords = _iter_coordinates(geojson["coordinates"])
    assert len(coords) > 0
    for lng, lat in coords:
        assert -180.0 <= lng <= 180.0
        assert -90.0 <= lat <= 90.0


def test_coordinates_are_rounded_to_bounded_precision() -> None:
    # A geometry whose UTM coordinates carry excessive decimal precision —
    # reprojection alone would otherwise emit the full float64 expansion.
    high_precision_square = Polygon(
        [
            (440280.123456789012, 4474247.987654321098),
            (440300.111111111111, 4474247.222222222222),
            (440300.333333333333, 4474267.444444444444),
            (440280.555555555555, 4474267.666666666666),
        ]
    )

    geojson = geometry_to_wgs84_geojson(high_precision_square)

    coords = _iter_coordinates(geojson["coordinates"])
    assert len(coords) > 0
    for lng, lat in coords:
        # ~6 decimal degrees precision (~0.1m); allow a small margin (7) for
        # floating point representation artifacts from the snap/reprojection.
        assert _max_decimal_places(lng) <= 7
        assert _max_decimal_places(lat) <= 7
