"""Unit tests for IngestSerZones use case."""

from unittest.mock import MagicMock

import pytest
from shapely.geometry import Polygon

from mobility_manager.application.use_cases.ingest_ser_zones import IngestSerZones
from mobility_manager.domain.value_objects.ser_zone_boundary_record import (
    SerZoneBoundaryRecord,
)
from mobility_manager.domain.value_objects.zone_area import ZoneArea

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _make_record(**kwargs) -> SerZoneBoundaryRecord:
    defaults = {
        "zone_number": "163",
        "zone_type": "Azul",
        "district": "CENTRO",
        "street_names": ["ABADA", "GRAN VIA"],
        "spot_count": 15,
        "geometry": _SQUARE,
    }
    defaults.update(kwargs)
    return SerZoneBoundaryRecord(**defaults)


def _make_zone_area(**kwargs) -> ZoneArea:
    defaults = {
        "zone_number": "163",
        "neighbourhood": "Sol",
        "geometry": _SQUARE,
    }
    defaults.update(kwargs)
    return ZoneArea(**defaults)


def test_execute_maps_records_to_repo_dicts_and_persists() -> None:
    provider = MagicMock()
    provider.city_code = "madrid"
    provider.get_records.return_value = [_make_record()]
    provider.get_zone_areas.return_value = [_make_zone_area()]

    repo = MagicMock()
    repo.bulk_replace.return_value = 1

    use_case = IngestSerZones(provider=provider, repo=repo)
    summary = use_case.execute()

    assert summary == {"total": 1, "inserted": 1}
    repo.bulk_replace.assert_called_once()
    (call_arg,) = repo.bulk_replace.call_args.args
    assert len(call_arg) == 1
    row = call_arg[0]
    assert row["zone_number"] == "163"
    assert row["zone_type"] == "Azul"
    assert row["district"] == "CENTRO"
    assert row["spot_count"] == 15
    assert row["street_names"] == ["ABADA", "GRAN VIA"]
    assert "POLYGON" in row["geometry_wkt"]

    zone_area_rows = repo.bulk_replace.call_args.kwargs["zone_areas"]
    assert len(zone_area_rows) == 1
    zone_area_row = zone_area_rows[0]
    assert zone_area_row["zone_number"] == "163"
    assert zone_area_row["neighbourhood"] == "Sol"
    assert "POLYGON" in zone_area_row["geometry_wkt"]


def test_execute_raises_and_does_not_touch_repo_for_empty_records() -> None:
    """
    An empty result must be treated the same as a fetch/parse failure: abort
    the run, never call bulk_replace, and propagate a real failure signal so
    existing data is not silently wiped (design.md: "any fetch/parse failure
    aborts the run and leaves existing data intact").
    """
    provider = MagicMock()
    provider.city_code = "madrid"
    provider.get_records.return_value = []

    repo = MagicMock()

    use_case = IngestSerZones(provider=provider, repo=repo)

    with pytest.raises(RuntimeError):
        use_case.execute()

    repo.bulk_replace.assert_not_called()


def test_execute_raises_and_does_not_touch_repo_when_provider_raises() -> None:
    """
    When provider.get_records() raises (simulating any of the sources
    failing), bulk_replace must never be called — the failure must propagate
    before any persistence is attempted.
    """
    provider = MagicMock()
    provider.city_code = "madrid"
    provider.get_records.side_effect = RuntimeError("HTTP 500 fetching source")

    repo = MagicMock()

    use_case = IngestSerZones(provider=provider, repo=repo)

    with pytest.raises(RuntimeError):
        use_case.execute()

    repo.bulk_replace.assert_not_called()


def test_execute_raises_and_does_not_touch_repo_when_zone_areas_empty() -> None:
    """
    records non-empty but zone_areas empty must abort the same way a
    records-empty result does — the exact partial-write bug found in the
    discarded Voronoi-based attempt's review pass (design.md risks /
    ser-zone-ingestion spec: "Zero resolved zone areas while records is
    non-empty also aborts the run").
    """
    provider = MagicMock()
    provider.city_code = "madrid"
    provider.get_records.return_value = [_make_record()]
    provider.get_zone_areas.return_value = []

    repo = MagicMock()

    use_case = IngestSerZones(provider=provider, repo=repo)

    with pytest.raises(RuntimeError):
        use_case.execute()

    repo.bulk_replace.assert_not_called()


def test_get_records_and_get_zone_areas_are_each_called_exactly_once() -> None:
    """
    Resilience test (design.md D7 of add-ser-zone-frontiers): IngestSerZones
    itself introduces no caching around the provider calls — each method is
    invoked exactly once per execute() call, with no memoization wrapper.
    """
    provider = MagicMock()
    provider.city_code = "madrid"
    provider.get_records.return_value = [_make_record()]
    provider.get_zone_areas.return_value = [_make_zone_area()]

    repo = MagicMock()
    repo.bulk_replace.return_value = 1

    use_case = IngestSerZones(provider=provider, repo=repo)
    use_case.execute()

    provider.get_records.assert_called_once()
    provider.get_zone_areas.assert_called_once()
