"""
Infrastructure: buffer and dissolve SER bands into zone boundary polygons.

Buffers every retained band's polyline with a single fixed half-width
(regardless of parking orientation — see design.md D4), groups the resulting
polygons by (zone_number, zone_type), and dissolves each group into one
SerZoneBoundaryRecord via shapely.ops.unary_union.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from shapely.ops import unary_union

from mobility_manager.domain.value_objects.ser_zone_boundary_record import (
    SerZoneBoundaryRecord,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    JoinedBand,
)

logger = logging.getLogger(__name__)

# Half-width (metres) applied uniformly to every band when buffering into a
# polygon — a coarse containment check does not need per-bay geometric
# precision (parking orientation is deliberately not modelled). See
# design.md D4. This is an estimate, not a verified Madrid regulation figure.
BAND_BUFFER_HALF_WIDTH_METERS = 2.5

# Simplification tolerance (metres, topology-preserving) applied to each
# zone's dissolved geometry before storage. See design.md D10: the buffer
# half-width above is itself only a 2.5m estimate, so sub-meter precision in
# the dissolved output serves no purpose, while an unsimplified union of
# hundreds of band parts produces impractically large geometry — measured at
# 3.6MB of WKT for a single zone (936 parts, 72,630 coordinates) and 74MB for
# the full bulk endpoint response against real Madrid data. A 0.5m tolerance
# cut that zone's coordinate count ~7x while preserving 97.9% of its area.
ZONE_GEOMETRY_SIMPLIFY_TOLERANCE_METERS = 0.5


def buffer_and_dissolve(joined_bands: list[JoinedBand]) -> list[SerZoneBoundaryRecord]:
    """
    Buffer each joined band and dissolve by (zone_number, zone_type) into
    SerZoneBoundaryRecords.
    """
    groups: dict[tuple[str, str], list[JoinedBand]] = defaultdict(list)
    for jb in joined_bands:
        groups[(jb.zone_number, jb.band.zone_type)].append(jb)

    records: list[SerZoneBoundaryRecord] = []
    for (zone_number, zone_type), members in groups.items():
        polygons = [m.band.geometry.buffer(BAND_BUFFER_HALF_WIDTH_METERS) for m in members]
        geometry = unary_union(polygons)
        geometry = geometry.simplify(
            ZONE_GEOMETRY_SIMPLIFY_TOLERANCE_METERS, preserve_topology=True
        )

        spot_counts = [m.band.spot_count for m in members]
        known = [c for c in spot_counts if c >= 0]
        total_spot_count = sum(known) if known else -1

        street_names = sorted({m.street_name for m in members})
        district = members[0].district

        records.append(
            SerZoneBoundaryRecord(
                zone_number=zone_number,
                zone_type=zone_type,
                district=district,
                street_names=street_names,
                spot_count=total_spot_count,
                geometry=geometry,
            )
        )

    logger.info(
        "Dissolved %d joined bands into %d zone boundary records",
        len(joined_bands),
        len(records),
    )
    return records
