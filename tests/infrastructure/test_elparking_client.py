"""
Unit tests for ElParkingClient.

HTTP calls are exercised via httpx.MockTransport so tests run without any
real network access. Confirms every authenticated call uses HTTP Basic auth
(blank username, access token as password) plus the ep-app-name/ep-app-version
headers, and that logout no longer sends Authorization: Bearer.
"""

import json

import httpx
import pytest

from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
)
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.client import (
    ElParkingClient,
)

_BASE_URL = "https://elparking.example.test"
_APP_VERSION = "26.2"
_ACCESS_TOKEN = "fake-test-access-token-value"


def _make_client() -> ElParkingClient:
    return ElParkingClient(base_url=_BASE_URL, app_version=_APP_VERSION)


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Patch httpx.Client so every request is routed through `handler`."""
    transport = httpx.MockTransport(handler)
    original_client_cls = httpx.Client

    def _fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _fake_client)


def _assert_basic_auth(request: httpx.Request) -> None:
    """Assert the request used HTTP Basic auth (blank username, access token as password), not Bearer."""
    assert "Authorization" in request.headers
    assert not request.headers["Authorization"].startswith("Bearer")
    import base64

    scheme, encoded = request.headers["Authorization"].split(" ", 1)
    assert scheme == "Basic"
    decoded = base64.b64decode(encoded).decode()
    assert decoded == f":{_ACCESS_TOKEN}"


def _assert_app_headers(request: httpx.Request) -> None:
    assert request.headers["ep-app-name"] == "elparking"
    assert request.headers["ep-app-version"] == _APP_VERSION


# --- login() ---


def test_login_returns_minimal_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/logins"
        _assert_app_headers(request)
        return httpx.Response(200, json={"id": 987, "access_token": _ACCESS_TOKEN})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    session = client.login(SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"}))

    assert session.data == {"access_token": _ACCESS_TOKEN, "device_session_id": 987}


def test_login_invalid_credentials_raises_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid credentials"})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderAuthenticationError):
        client.login(SerProviderCredentials(data={"email": "alice@example.com", "password": "wrong"}))


def test_login_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.login(SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"}))


def test_login_connection_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.login(SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"}))


# --- logout() ---


def test_logout_uses_basic_auth_not_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url == f"{_BASE_URL}/v1/logins/{_ACCESS_TOKEN}"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        return httpx.Response(204)

    _patch_client(monkeypatch, handler)
    client = _make_client()

    client.logout(_ACCESS_TOKEN)


def test_logout_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.logout(_ACCESS_TOKEN)


def test_logout_connection_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.logout(_ACCESS_TOKEN)


# --- list_vehicles() ---


def test_list_vehicles_uses_basic_auth_and_app_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/users/me/vehicles"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        return httpx.Response(200, json=[{"id": 1, "license_plate": "1234ABC"}])

    _patch_client(monkeypatch, handler)
    client = _make_client()

    vehicles = client.list_vehicles(_ACCESS_TOKEN)

    assert vehicles == [{"id": 1, "license_plate": "1234ABC"}]


def test_list_vehicles_unexpected_shape_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.list_vehicles(_ACCESS_TOKEN)


def test_list_vehicles_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.list_vehicles(_ACCESS_TOKEN)


# --- list_towns() ---


def test_list_towns_uses_basic_auth_and_app_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/ser-towns"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        return httpx.Response(200, json=[{"id": "town-1", "name": "Madrid"}])

    _patch_client(monkeypatch, handler)
    client = _make_client()

    towns = client.list_towns(_ACCESS_TOKEN)

    assert towns == [{"id": "town-1", "name": "Madrid"}]


def test_list_towns_unexpected_shape_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.list_towns(_ACCESS_TOKEN)


# --- list_zones() ---


def test_list_zones_uses_basic_auth_and_app_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/ser-zones/town-1"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        return httpx.Response(200, json=[{"id": "zone-1", "name": "84 - PILAR", "polygon_wkt": "POLYGON EMPTY"}])

    _patch_client(monkeypatch, handler)
    client = _make_client()

    zones = client.list_zones(_ACCESS_TOKEN, "town-1")

    assert zones == [{"id": "zone-1", "name": "84 - PILAR", "polygon_wkt": "POLYGON EMPTY"}]


def test_list_zones_unexpected_shape_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.list_zones(_ACCESS_TOKEN, "town-1")


# --- get_steps() ---


def test_get_steps_uses_basic_auth_and_app_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/ser-steps/zone/zone-1/rate/rate-1/vehicle/42"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        return httpx.Response(200, json={"steps": [{"stay_duration": 60, "fare_qty": 1.5, "step_request": "opaque"}]})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    steps = client.get_steps(_ACCESS_TOKEN, "zone-1", "rate-1", 42)

    assert steps == {"steps": [{"stay_duration": 60, "fare_qty": 1.5, "step_request": "opaque"}]}


def test_get_steps_unexpected_shape_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.get_steps(_ACCESS_TOKEN, "zone-1", "rate-1", 42)


# --- create_ticket() ---


def test_create_ticket_uses_basic_auth_and_app_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == f"{_BASE_URL}/v1/ser-tickets"
        _assert_basic_auth(request)
        _assert_app_headers(request)
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "ticket-1", "total_qty": 1.5, "end_date": "2026-07-23T12:00:00+00:00"})

    _patch_client(monkeypatch, handler)
    client = _make_client()

    body = {"id_vehicle": 1, "id_ser_zone": "zone-1", "id_ser_rate": "rate-1"}
    response = client.create_ticket(_ACCESS_TOKEN, body)

    assert captured["body"] == body
    assert response == {"id": "ticket-1", "total_qty": 1.5, "end_date": "2026-07-23T12:00:00+00:00"}


def test_create_ticket_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.create_ticket(_ACCESS_TOKEN, {})


def test_create_ticket_connection_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.create_ticket(_ACCESS_TOKEN, {})


def test_create_ticket_malformed_body_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, text="not json at all")

    _patch_client(monkeypatch, handler)
    client = _make_client()

    with pytest.raises(SerProviderApiError):
        client.create_ticket(_ACCESS_TOKEN, {})
