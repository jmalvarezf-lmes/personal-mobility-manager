"""
Unit tests for ElParkingSerTicketProvider.login().

HTTP calls are exercised via httpx.MockTransport so tests run without any
real network access.
"""

import httpx
import pytest

from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
)
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.provider import (
    ElParkingSerTicketProvider,
)

_BASE_URL = "https://elparking.example.test"


@pytest.fixture(autouse=True)
def _elparking_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELPARKING_API_BASE_URL", _BASE_URL)


def _make_provider() -> ElParkingSerTicketProvider:
    return ElParkingSerTicketProvider()


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Patch httpx.Client so every request is routed through `handler`."""
    transport = httpx.MockTransport(handler)
    original_client_cls = httpx.Client

    def _fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _fake_client)


def test_successful_login_returns_minimal_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{_BASE_URL}/v1/logins"
        assert request.headers["ep-app-name"] == "elparking"
        assert request.headers["ep-app-version"] == "26.2"
        return httpx.Response(
            200,
            json={
                "id": 987,
                "access_token": "fake-test-access-token-value",
                "user": {"id": 1, "name": "Alice"},
                "application": 0,
                "login_type": 0,
                "push": None,
                "language": "es",
                "model": "personal-mobility-manager-server",
            },
        )

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(
        data={"email": "alice@example.com", "password": "s3cr3t", "uid": "abc", "model": "server"}
    )

    session = provider.login(credentials)

    assert session.data == {
        "access_token": "fake-test-access-token-value",
        "device_session_id": 987,
    }


def test_login_uses_ep_app_version_from_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELPARKING_APP_VERSION", "27.0")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["ep-app-version"] == "27.0"
        return httpx.Response(200, json={"id": 1, "access_token": "tok"})

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})
    provider.login(credentials)


def test_login_sends_uid_and_model_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 1, "access_token": "tok"})

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(
        data={"email": "alice@example.com", "password": "s3cr3t", "uid": "42", "model": "server-model"}
    )
    provider.login(credentials)

    assert captured["body"] == {
        "email": "alice@example.com",
        "password": "s3cr3t",
        "uid": "42",
        "model": "server-model",
    }


def test_login_omits_uid_and_model_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 1, "access_token": "tok"})

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})
    provider.login(credentials)

    assert captured["body"] == {"email": "alice@example.com", "password": "s3cr3t"}


def test_invalid_credentials_raise_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid credentials"})

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "wrong"})

    with pytest.raises(SerProviderAuthenticationError):
        provider.login(credentials)


def test_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    with pytest.raises(SerProviderApiError):
        provider.login(credentials)


def test_rate_limited_response_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="too many requests")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    with pytest.raises(SerProviderApiError):
        provider.login(credentials)


def test_malformed_body_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 2xx but missing the expected fields
        return httpx.Response(200, json={"unexpected": "shape"})

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    with pytest.raises(SerProviderApiError):
        provider.login(credentials)


def test_non_json_body_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    with pytest.raises(SerProviderApiError):
        provider.login(credentials)


def test_connection_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    with pytest.raises(SerProviderApiError):
        provider.login(credentials)


def test_successful_logout_sends_delete_with_bearer_header(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url == f"{_BASE_URL}/v1/logins/fake-test-access-token-value"
        assert request.headers["Authorization"] == "Bearer fake-test-access-token-value"
        return httpx.Response(204)

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    session = SerProviderSession(data={"access_token": "fake-test-access-token-value", "device_session_id": 1})

    provider.logout(session)


def test_logout_server_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    session = SerProviderSession(data={"access_token": "tok"})

    with pytest.raises(SerProviderApiError):
        provider.logout(session)


def test_logout_connection_error_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()
    session = SerProviderSession(data={"access_token": "tok"})

    with pytest.raises(SerProviderApiError):
        provider.logout(session)


def test_create_ticket_raises_not_implemented_without_http_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("create_ticket must not make any HTTP call")

    _patch_client(monkeypatch, handler)

    provider = _make_provider()

    with pytest.raises(NotImplementedError):
        provider.create_ticket(session=None, vehicle=None, duration_minutes=60)  # type: ignore[arg-type]
