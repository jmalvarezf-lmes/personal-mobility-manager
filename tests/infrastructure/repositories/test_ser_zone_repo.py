"""
Unit tests for PostgresSerZoneRepository.list_all() row-level error isolation.

Uses a mocked SQLAlchemy Engine/Connection so this runs with no real
PostgreSQL instance (unlike test_ser_zone_repo_integration.py, which is
skipped without POSTGRES_DSN). Only list_all()'s per-row try/except is
covered here — full round-trip behaviour is covered by the integration test.
"""

from unittest.mock import MagicMock

from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)

_VALID_WKT = "POLYGON((440584 4474459, 440604 4474459, 440604 4474479, 440584 4474479, 440584 4474459))"


def _make_engine_with_rows(rows: list[tuple]) -> MagicMock:
    """Build a mocked Engine whose connect().execute().fetchall() returns rows."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = rows
    return engine


def test_list_all_skips_row_with_invalid_geometry_and_keeps_valid_rows() -> None:
    rows = [
        ("madrid", "100", "Azul", "CENTRO", 5, _VALID_WKT),
        ("madrid", "200", "Verde", "CENTRO", 3, "NOT VALID WKT"),
        ("madrid", "300", "Rojo", "CENTRO", 7, _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    zone_numbers = {z.zone_number for z in zones}
    assert zone_numbers == {"100", "300"}
    assert len(zones) == 2


def test_list_all_returns_empty_list_when_all_rows_invalid() -> None:
    rows = [
        ("madrid", "100", "Azul", "CENTRO", 5, "garbage"),
        ("madrid", "200", "Verde", "CENTRO", 3, "also garbage"),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    assert zones == []


def test_list_all_returns_all_rows_when_all_valid() -> None:
    rows = [
        ("madrid", "100", "Azul", "CENTRO", 5, _VALID_WKT),
        ("madrid", "200", "Verde", "CENTRO", 3, _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    assert len(zones) == 2


# ---------------------------------------------------------------------------
# get_zone_area / list_zone_areas
# ---------------------------------------------------------------------------


def _make_engine_with_fetchone(row: tuple | None) -> MagicMock:
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchone.return_value = row
    return engine


def test_get_zone_area_returns_zone_area_for_known_zone_number() -> None:
    engine = _make_engine_with_fetchone(("madrid", "163", "Sol", _VALID_WKT))
    repo = PostgresSerZoneRepository(engine)

    zone_area = repo.get_zone_area("madrid", "163")

    assert zone_area is not None
    assert zone_area.zone_number == "163"
    assert zone_area.neighbourhood == "Sol"
    assert zone_area.geometry.is_valid


def test_get_zone_area_returns_none_for_unknown_zone_number() -> None:
    engine = _make_engine_with_fetchone(None)
    repo = PostgresSerZoneRepository(engine)

    assert repo.get_zone_area("madrid", "999") is None


def test_get_zone_area_returns_none_for_invalid_geometry() -> None:
    engine = _make_engine_with_fetchone(("madrid", "163", "Sol", "NOT VALID WKT"))
    repo = PostgresSerZoneRepository(engine)

    assert repo.get_zone_area("madrid", "163") is None


def test_list_zone_areas_returns_all_rows() -> None:
    rows = [
        ("madrid", "100", "Palacio", _VALID_WKT),
        ("madrid", "200", "Sol", _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 2
    assert {za.zone_number for za in zone_areas} == {"100", "200"}


def test_list_zone_areas_skips_invalid_geometry_row() -> None:
    rows = [
        ("madrid", "100", "Palacio", _VALID_WKT),
        ("madrid", "200", "Sol", "garbage"),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "100"


# ---------------------------------------------------------------------------
# list_zones_for_city / list_zone_areas_for_city (see
# add-vehicle-ser-parking-exemption design.md D7)
# ---------------------------------------------------------------------------


def _make_engine_capturing_query_and_params() -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    return engine, conn


def test_list_zones_for_city_issues_a_where_city_code_clause_with_the_given_city() -> None:
    engine, conn = _make_engine_capturing_query_and_params()
    conn.execute.return_value.fetchall.return_value = [
        ("madrid", "100", "Azul", "CENTRO", 5, _VALID_WKT),
    ]
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_zones_for_city("madrid")

    assert len(zones) == 1
    assert zones[0].zone_number == "100"
    call = conn.execute.call_args
    sql = str(call.args[0])
    params = call.args[1]
    assert "WHERE city_code = :city_code" in sql
    assert params == {"city_code": "madrid"}


def test_list_zones_for_city_skips_invalid_geometry_row() -> None:
    engine, conn = _make_engine_capturing_query_and_params()
    conn.execute.return_value.fetchall.return_value = [
        ("madrid", "100", "Azul", "CENTRO", 5, _VALID_WKT),
        ("madrid", "200", "Verde", "CENTRO", 3, "garbage"),
    ]
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_zones_for_city("madrid")

    assert len(zones) == 1
    assert zones[0].zone_number == "100"


def test_list_zone_areas_for_city_issues_a_where_city_code_clause_with_the_given_city() -> None:
    engine, conn = _make_engine_capturing_query_and_params()
    conn.execute.return_value.fetchall.return_value = [
        ("madrid", "100", "Palacio", _VALID_WKT),
    ]
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas_for_city("madrid")

    assert len(zone_areas) == 1
    assert zone_areas[0].neighbourhood == "Palacio"
    call = conn.execute.call_args
    sql = str(call.args[0])
    params = call.args[1]
    assert "WHERE city_code = :city_code" in sql
    assert params == {"city_code": "madrid"}


def test_list_zone_areas_for_city_skips_invalid_geometry_row() -> None:
    engine, conn = _make_engine_capturing_query_and_params()
    conn.execute.return_value.fetchall.return_value = [
        ("madrid", "100", "Palacio", _VALID_WKT),
        ("madrid", "200", "Sol", "garbage"),
    ]
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas_for_city("madrid")

    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "100"


# ---------------------------------------------------------------------------
# get_street_names / get_zone_area: filtering when two cities share a
# zone_number/zone_type (see add-ser-enforcement-calendar tasks.md 8.5)
# ---------------------------------------------------------------------------


def _make_engine_dispatching_on_params(rows_by_key: dict[tuple, object], *, many: bool) -> MagicMock:
    """
    Build a mocked Engine whose connect().execute(query, params) looks up a
    canned result keyed by a tuple of `params` values (in the order the key
    dict was built with), simulating city-scoped filtering against a fake
    "database" that holds rows for more than one city.
    """
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    def _execute(query: object, params: dict) -> MagicMock:
        key = tuple(params.values())
        result = MagicMock()
        if many:
            result.fetchall.return_value = rows_by_key.get(key, [])
        else:
            result.fetchone.return_value = rows_by_key.get(key)
        return result

    conn.execute.side_effect = _execute
    return engine


def test_get_street_names_filters_by_city_when_two_cities_share_zone_number_and_zone_type() -> None:
    engine = _make_engine_dispatching_on_params(
        {
            ("madrid", "100", "Azul"): [("GRAN VIA",)],
            ("barcelona", "100", "Azul"): [("DIAGONAL",)],
        },
        many=True,
    )
    repo = PostgresSerZoneRepository(engine)

    assert repo.get_street_names("madrid", "100", "Azul") == ["GRAN VIA"]
    assert repo.get_street_names("barcelona", "100", "Azul") == ["DIAGONAL"]


def test_get_zone_area_filters_by_city_when_two_cities_share_zone_number() -> None:
    engine = _make_engine_dispatching_on_params(
        {
            ("madrid", "100"): ("madrid", "100", "Palacio", _VALID_WKT),
            ("barcelona", "100"): ("barcelona", "100", "Eixample", _VALID_WKT),
        },
        many=False,
    )
    repo = PostgresSerZoneRepository(engine)

    madrid_area = repo.get_zone_area("madrid", "100")
    barcelona_area = repo.get_zone_area("barcelona", "100")

    assert madrid_area is not None
    assert barcelona_area is not None
    assert madrid_area.neighbourhood == "Palacio"
    assert barcelona_area.neighbourhood == "Eixample"
    assert madrid_area.zone_number == barcelona_area.zone_number == "100"
    assert madrid_area.city_code != barcelona_area.city_code


# ---------------------------------------------------------------------------
# bulk_replace(): city-scoped DELETE, not a bare TRUNCATE (see design.md D6
# and add-ser-enforcement-calendar tasks.md 8.4)
# ---------------------------------------------------------------------------


def _make_engine_for_bulk_replace() -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    return engine, conn


def _bulk_replace_zone_record(city_code: str = "madrid", zone_number: str = "163") -> dict:
    return {
        "city_code": city_code,
        "zone_number": zone_number,
        "zone_type": "Azul",
        "district": "CENTRO",
        "spot_count": 5,
        "geometry_wkt": _VALID_WKT,
        "street_names": ["ABADA"],
    }


def test_bulk_replace_deletes_are_scoped_to_the_ingested_city_code_not_a_truncate() -> None:
    """
    ser_zones/ser_zone_streets: unchanged scoped text() DELETEs. ser_zone_areas:
    no zone_areas passed here (empty zone_area_rows), so it still hits the
    "delete all rows for this city" edge-case path — via a Core
    .delete().where() construct, not text() — see
    add-vehicle-ser-parking-exemption tasks.md 11.4.
    """
    engine, conn = _make_engine_for_bulk_replace()
    repo = PostgresSerZoneRepository(engine)

    repo.bulk_replace([_bulk_replace_zone_record(city_code="madrid")])

    text_delete_calls = [
        call
        for call in conn.execute.call_args_list
        if "DELETE" in str(call.args[0]) and "ser_zone_areas" not in str(call.args[0])
    ]
    assert len(text_delete_calls) == 2  # ser_zones, ser_zone_streets
    for call in text_delete_calls:
        sql = str(call.args[0])
        params = call.args[1]
        assert "TRUNCATE" not in sql
        assert "WHERE city_code = :city_code" in sql
        assert params == {"city_code": "madrid"}

    core_delete_calls = [
        call for call in conn.execute.call_args_list if "DELETE" in str(call.args[0]) and "ser_zone_areas" in str(call.args[0])
    ]
    assert len(core_delete_calls) == 1
    core_delete_sql = str(core_delete_calls[0].args[0])
    assert "TRUNCATE" not in core_delete_sql
    assert "ser_zone_areas" in core_delete_sql
    assert "city_code" in core_delete_sql


def test_bulk_replace_scopes_delete_to_the_specific_city_being_ingested() -> None:
    """Ingesting barcelona's records must scope every DELETE to 'barcelona', not 'madrid' or an unscoped delete."""
    engine, conn = _make_engine_for_bulk_replace()
    repo = PostgresSerZoneRepository(engine)

    repo.bulk_replace([_bulk_replace_zone_record(city_code="barcelona")])

    text_delete_calls = [
        call
        for call in conn.execute.call_args_list
        if "DELETE" in str(call.args[0]) and "ser_zone_areas" not in str(call.args[0])
    ]
    assert len(text_delete_calls) == 2
    for call in text_delete_calls:
        assert call.args[1] == {"city_code": "barcelona"}

    core_delete_calls = [
        call for call in conn.execute.call_args_list if "DELETE" in str(call.args[0]) and "ser_zone_areas" in str(call.args[0])
    ]
    assert len(core_delete_calls) == 1


def test_bulk_replace_upserts_ser_zone_areas_when_zone_areas_provided_not_delete_then_insert() -> None:
    """
    When zone_areas is non-empty, ser_zone_areas must be upserted (INSERT ...
    ON CONFLICT DO UPDATE), never delete-then-insert — a blanket DELETE would
    violate vehicle_ser_parking_exemptions' composite FK for any vehicle with
    a saved exemption referencing a still-live zone_number. See
    add-vehicle-ser-parking-exemption tasks.md 11.4.
    """
    engine, conn = _make_engine_for_bulk_replace()
    repo = PostgresSerZoneRepository(engine)

    repo.bulk_replace(
        [_bulk_replace_zone_record(city_code="madrid", zone_number="163")],
        zone_areas=[
            {
                "city_code": "madrid",
                "zone_number": "163",
                "neighbourhood": "Sol",
                "geometry_wkt": _VALID_WKT,
            }
        ],
    )

    # No unconditional "DELETE FROM ser_zone_areas WHERE city_code = ..." text() call
    # (that unscoped-by-zone_number form is what used to violate the FK).
    unconditional_delete_calls = [
        call
        for call in conn.execute.call_args_list
        if "DELETE" in str(call.args[0]) and "ser_zone_areas" in str(call.args[0]) and "NOT IN" not in str(call.args[0])
    ]
    assert unconditional_delete_calls == []

    insert_calls = [
        call for call in conn.execute.call_args_list if "INSERT" in str(call.args[0]) and "ON CONFLICT" in str(call.args[0])
    ]
    assert len(insert_calls) == 1

    # A targeted DELETE (retired zones only) is still issued via the Core delete() construct.
    core_delete_calls = [
        call
        for call in conn.execute.call_args_list
        if "DELETE" in str(call.args[0]) and "ser_zone_areas" in str(call.args[0])
    ]
    assert len(core_delete_calls) == 1
    assert "NOT IN" in str(core_delete_calls[0].args[0])


def test_bulk_replace_with_empty_records_is_a_no_op() -> None:
    """
    Empty records: no delete/insert issued at all, and 0 is returned — with
    no city_code available from an empty records list, there's nothing to
    scope a DELETE to, so this is a true no-op rather than a destructive
    fallback.
    """
    engine, conn = _make_engine_for_bulk_replace()
    repo = PostgresSerZoneRepository(engine)

    inserted = repo.bulk_replace([])

    assert inserted == 0
    engine.begin.assert_not_called()
    conn.execute.assert_not_called()
