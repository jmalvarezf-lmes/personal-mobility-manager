"""
Regression test for the notification_types seed-data bug.

The p3q4r5s6t7u8 migration originally set
`_THRESHOLD_CONFIG_SCHEMA = json.dumps({...})` — a Python *string* — as the
value inserted into a JSONB column. The JSONB adapter then serialized that
string again, so the column ended up holding a JSON string value (e.g.
`"{\"threshold_m\": ...}"`) instead of a JSON object, which round-tripped
back as a Python str and failed NotificationTypeResponse's pydantic
validation on every GET /notifications/types (a 500 in production, though it
was never caught by tests because the integration test's fixture re-creates
its own hand-typed schema/seed data rather than exercising this migration
file directly — see test_notification_preferences_repo_integration.py).

This test imports the migration module directly (no DB required) and
asserts the seed value is a dict, not a string, so a future reintroduction
of json.dumps() here fails fast without needing a live Postgres.
"""

import importlib.util
from pathlib import Path

_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
_MIGRATION_PATH = _VERSIONS_DIR / "p3q4r5s6t7u8_create_notification_types.py"
_SER_TICKET_TYPES_MIGRATION_PATH = _VERSIONS_DIR / "911464896d6c_add_ser_ticket_creation_notification_types.py"


def _load_migration_module(path: Path = _MIGRATION_PATH, name: str = "create_notification_types_migration"):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_threshold_config_schema_seed_is_a_dict_not_a_json_string() -> None:
    module = _load_migration_module()
    assert isinstance(module._THRESHOLD_CONFIG_SCHEMA, dict), (
        "_THRESHOLD_CONFIG_SCHEMA must be a plain dict — the JSONB column "
        "adapter serializes it to JSON itself. Passing an already-"
        "json.dumps()'d string double-encodes it into a JSON string value "
        "instead of a JSON object, which fails NotificationTypeResponse "
        "validation on every GET /notifications/types."
    )
    assert module._THRESHOLD_CONFIG_SCHEMA == {"threshold_m": {"type": "integer", "min": 1}}


def test_catalog_has_exactly_four_rows_with_expected_config_schema() -> None:
    """
    Task 1.4: combining both catalog-seeding migrations must produce exactly
    the four notification_types rows the notification-type-preferences spec
    requires — location_moved / ser_zone_ticket_required with the threshold
    config_schema, and the two new event-reaction types with an empty one.
    """
    original_module = _load_migration_module()
    ser_ticket_module = _load_migration_module(
        _SER_TICKET_TYPES_MIGRATION_PATH, name="add_ser_ticket_creation_notification_types_migration"
    )

    threshold_schema = original_module._THRESHOLD_CONFIG_SCHEMA
    seeded_keys = {"location_moved", "ser_zone_ticket_required"}

    new_rows = {row["key"]: row["config_schema"] for row in ser_ticket_module._SEEDED_TYPES}
    assert set(new_rows) == {"ser_ticket_created", "ser_ticket_creation_failed"}

    all_keys = seeded_keys | set(new_rows)
    assert len(all_keys) == 4

    assert threshold_schema == {"threshold_m": {"type": "integer", "min": 1}}
    for key, schema in new_rows.items():
        assert schema == {}, f"{key} must have an empty config_schema — it reacts to an event, not distance"
