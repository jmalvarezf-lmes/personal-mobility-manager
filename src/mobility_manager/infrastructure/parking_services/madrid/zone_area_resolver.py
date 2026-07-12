"""
Infrastructure: zone_number -> ZoneArea (frontier) resolution via
compound-code majority vote + Barrios lookup.

Replaces the discarded Voronoi-tessellation frontier computation. For each
zone_number, computes the majority (district_code, barrio_code) pair by
matched-address-point count (the same majority-vote pattern already used for
other per-zone attributes), formats it as "{district_code}-{barrio_code}"
(stripping any zero-padding, since the Barrios shapefile's COD_DISB field is
unpadded, e.g. "1-6" not "01-06"), and looks that compound key up directly
against the parsed Barrios records. See design.md D2/D3/D5 of
add-ser-zone-frontiers.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from mobility_manager.domain.value_objects.zone_area import ZoneArea
from mobility_manager.infrastructure.parking_services.madrid.barrios_shapefile import (
    BarrioRecord,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    JoinedBand,
)

logger = logging.getLogger(__name__)


def _compound_code(district_code: str, barrio_code: str) -> str | None:
    """
    Format a (district_code, barrio_code) pair as a Barrios-style compound
    code (e.g. "1-6"), stripping any zero-padding the callejero CSV may
    carry. Returns None if either code is not a valid integer string.
    """
    try:
        return f"{int(district_code)}-{int(barrio_code)}"
    except ValueError:
        return None


def compute_majority_compound_codes(bands: list[JoinedBand]) -> dict[str, str]:
    """
    For each zone_number, compute its majority (district_code, barrio_code)
    compound code by matched-address-point count (i.e. by band count, since
    each band already inherited its nearest callejero point's codes).

    Ties are broken deterministically via Counter.most_common()'s stable
    ordering (first-encountered compound code among the tied candidates
    wins). Bands whose district_code/barrio_code cannot be parsed as
    integers are excluded from the vote for that zone_number.

    Returns a dict mapping zone_number -> compound code string (e.g. "1-6").
    zone_numbers with no valid compound code among their bands are absent.
    """
    votes: dict[str, Counter[str]] = defaultdict(Counter)

    for band in bands:
        compound = _compound_code(band.district_code, band.barrio_code)
        if compound is None:
            continue
        votes[band.zone_number][compound] += 1

    majority: dict[str, str] = {}
    for zone_number, counter in votes.items():
        if not counter:
            continue
        majority[zone_number] = counter.most_common(1)[0][0]

    return majority


def resolve_zone_areas(
    bands: list[JoinedBand],
    barrio_records: list[BarrioRecord],
) -> list[ZoneArea]:
    """
    Resolve one ZoneArea per zone_number whose majority compound code
    matches a Barrios record.

    A zone_number whose majority compound code does not match any Barrios
    record is skipped entirely (absent from the result) and a warning is
    logged — no fallback/synthesized geometry is produced (design.md D5).
    """
    majority_codes = compute_majority_compound_codes(bands)
    barrios_by_code = {r.cod_disb: r for r in barrio_records}

    zone_areas: list[ZoneArea] = []
    skipped = 0
    for zone_number, compound_code in majority_codes.items():
        barrio = barrios_by_code.get(compound_code)
        if barrio is None:
            logger.warning(
                "Skipping frontier for zone_number %r — majority compound code %r "
                "did not match any Barrios record",
                zone_number,
                compound_code,
            )
            skipped += 1
            continue

        zone_areas.append(
            ZoneArea(
                zone_number=zone_number,
                neighbourhood=barrio.nombre,
                geometry=barrio.geometry,
            )
        )

    logger.info(
        "Resolved %d zone_number frontiers via compound-code lookup, %d skipped (no matching Barrios record)",
        len(zone_areas),
        skipped,
    )
    return zone_areas
