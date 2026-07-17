"""
Tests for app.py's lifespan wiring of OpenTelemetry observability.

Activation is implicit (see design.md decision 3): init_observability() must
only be called when OTEL_EXPORTER_OTLP_ENDPOINT is configured, and the app
must start and serve /health identically either way. All other startup
wiring (Madrid ingestion providers, ElParking/Toyota pull providers) is
disabled via env vars below so this stays a fast, network-free unit test —
matching this sandbox's "no live Postgres/network" constraint, since none
of the disabled paths ever execute a real query or outbound call at
construction time.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_REQUIRED_ENV = {
    "POSTGRES_DSN": "postgresql://user:pass@localhost:5432/db",
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "TELEGRAM_BOT_USERNAME": "test_bot",
    "JWT_SECRET": "test-jwt-secret",
    "GOOGLE_CLIENT_ID": "test-client-id",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost/callback",
    # Skip ElParking construction (avoids ENCRYPTION_KEY/base URL requirement).
    "ENABLED_SER_PROVIDERS": "",
    # Skip Madrid provider construction (avoids real shapefile/CSV ingestion over the network).
    "ENABLED_CITIES": "",
    # Push-only: no Toyota pull provider, no ENCRYPTION_KEY requirement.
    "ENABLED_BRANDS": "generic",
}


@pytest.fixture
def _app_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    yield


def test_health_responds_normally_with_no_otel_endpoint_configured(_app_env: None) -> None:
    with patch("mobility_manager.presentation.api.app.init_observability") as mock_init:
        from mobility_manager.presentation.api.app import app

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_init.assert_not_called()


def test_init_observability_called_when_otel_endpoint_configured(
    _app_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    with (
        patch("mobility_manager.presentation.api.app.init_observability") as mock_init,
        patch("mobility_manager.presentation.api.app.shutdown_observability") as mock_shutdown,
    ):
        mock_init.return_value = (MagicMock(), MagicMock())
        from mobility_manager.presentation.api.app import app

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    mock_init.assert_called_once()
    mock_shutdown.assert_called_once()
