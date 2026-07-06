"""
Unit tests for TelegramNotificationChannel.send().

HTTP calls are exercised via httpx.MockTransport so tests run without any
real network access, mirroring test_elparking_provider.py's style.
"""

import httpx
import pytest

from mobility_manager.domain.exceptions import NotificationChannelApiError
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)
from mobility_manager.infrastructure.notification_channels.telegram.channel import (
    TelegramNotificationChannel,
)

_BOT_TOKEN = "fake-test-bot-token"


@pytest.fixture(autouse=True)
def _telegram_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", _BOT_TOKEN)


def _make_channel() -> TelegramNotificationChannel:
    return TelegramNotificationChannel()


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Patch httpx.Client so every request is routed through `handler`."""
    transport = httpx.MockTransport(handler)
    original_client_cls = httpx.Client

    def _fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _fake_client)


def test_successful_send_calls_send_message_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!")

    channel.send(recipient, message)

    assert captured["body"] == {"chat_id": 123456789, "text": "Hello!"}


def test_send_without_location_does_not_call_send_location(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!")

    channel.send(recipient, message)

    assert calls == [f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"]


def test_send_with_location_calls_both_send_message_and_send_location(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/sendMessage"):
            captured["send_message_body"] = json.loads(request.content)
        elif url.endswith("/sendLocation"):
            captured["send_location_body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!", location=GeoLocation(lat=40.4, lng=-3.7))

    channel.send(recipient, message)

    assert captured["send_message_body"] == {"chat_id": 123456789, "text": "Hello!"}
    assert captured["send_location_body"] == {
        "chat_id": 123456789,
        "latitude": 40.4,
        "longitude": -3.7,
    }


def test_send_location_failure_raises_notification_channel_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/sendLocation"):
            return httpx.Response(400, json={"ok": False, "description": "bad location"})
        return httpx.Response(200, json={"ok": True})

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!", location=GeoLocation(lat=40.4, lng=-3.7))

    with pytest.raises(NotificationChannelApiError):
        channel.send(recipient, message)


def test_non_2xx_response_raises_notification_channel_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "chat not found"})

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!")

    with pytest.raises(NotificationChannelApiError):
        channel.send(recipient, message)


def test_connection_error_raises_notification_channel_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _patch_client(monkeypatch, handler)

    channel = _make_channel()
    recipient = NotificationRecipient(data={"chat_id": 123456789})
    message = NotificationMessage(text="Hello!")

    with pytest.raises(NotificationChannelApiError):
        channel.send(recipient, message)
