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

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "p3q4r5s6t7u8_create_notification_types.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "create_notification_types_migration", _MIGRATION_PATH
    )
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
    assert module._THRESHOLD_CONFIG_SCHEMA == {
        "threshold_m": {"type": "integer", "min": 1}
    }
