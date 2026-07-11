"""
Presentation: UTM -> WGS84 GeoJSON reprojection helper.

Reused by both GET /parking/ser-zone and GET /parking/ser-zones to reproject
stored EPSG:25830 geometry to WGS84 GeoJSON at the API boundary (see
design.md D6 — canonical geometry stays in UTM in storage/domain, WGS84
GeoJSON is a serialization-time concern only).
"""

from typing import Any

import shapely
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

_utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

# Coordinate precision (decimal degrees) snapped onto reprojected WGS84
# geometry before serialization. ~1e-6 degrees is ~0.11m at Madrid's
# latitude, well past GPS positioning error and the pipeline's own 2.5m
# buffer estimate (design.md D4). Rounding here avoids emitting the full
# float64 decimal expansion on every coordinate, shrinking the bulk
# GET /parking/ser-zones JSON payload — see design.md D10.
WGS84_COORDINATE_PRECISION_DEGREES = 1e-6


def geometry_to_wgs84_geojson(geometry: BaseGeometry) -> dict[str, Any]:
    """Reproject an EPSG:25830 shapely geometry to WGS84 and return it as a GeoJSON dict."""
    wgs84_geometry = shapely_transform(_utm_to_wgs84.transform, geometry)
    wgs84_geometry = shapely.set_precision(
        wgs84_geometry, grid_size=WGS84_COORDINATE_PRECISION_DEGREES
    )
    return dict(mapping(wgs84_geometry))
