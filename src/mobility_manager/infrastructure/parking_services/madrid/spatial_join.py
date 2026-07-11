"""
Infrastructure: spatial join between SER bands and callejero address points.

Builds an STRtree over all callejero points and, for each retained band,
finds the nearest callejero point (by the band's midpoint) to inherit its
zone_number, street name, and district. See design.md D3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from shapely.geometry import Point
from shapely.strtree import STRtree

from mobility_manager.infrastructure.parking_services.madrid.callejero_parser import (
    CallejeroPoint,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    SerBand,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JoinedBand:
    """A SER band after being spatially joined to its nearest callejero point."""

    band: SerBand
    zone_number: str
    street_name: str
    district: str


def build_callejero_index(points: list[CallejeroPoint]) -> STRtree:
    """Build an STRtree over callejero points' UTM 25830 coordinates."""
    geometries = [Point(p.utm_x, p.utm_y) for p in points]
    return STRtree(geometries)


def join_bands_to_callejero(
    bands: list[SerBand],
    callejero_points: list[CallejeroPoint],
) -> list[JoinedBand]:
    """
    For each band, find the nearest callejero point (by band midpoint) and
    attach its zone_number/street_name/district.

    Returns an empty list if callejero_points is empty (no join target).
    """
    if not callejero_points:
        logger.warning("No callejero points available — cannot spatially join any bands")
        return []

    tree = build_callejero_index(callejero_points)

    joined: list[JoinedBand] = []
    for band in bands:
        midpoint = band.geometry.interpolate(0.5, normalized=True)
        nearest_idx = tree.nearest(midpoint)
        nearest_point = callejero_points[nearest_idx]

        joined.append(
            JoinedBand(
                band=band,
                zone_number=nearest_point.zone_number,
                street_name=nearest_point.street_name,
                district=nearest_point.district,
            )
        )

    return joined
