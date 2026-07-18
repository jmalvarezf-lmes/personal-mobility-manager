"""
Unit tests for GoogleCalendarHolidayProvider.

HTTP calls are exercised via httpx.MockTransport so tests run without any
real network access, following the same pattern as
tests/infrastructure/vehicle_providers/dgt/test_ambient_label_provider.py.

Covers the `public-holiday-calendar` spec's "Successful fetch",
"Fetch failure does not raise from within the provider silently",
"Hostname allowlist enforced", and "Configurable URL" scenarios (URL
override is exercised at the config.get_holiday_calendar_url() level in
tests/test_config.py-style tests — here it is exercised by constructing the
provider directly with a non-default, still-allowed URL).

The provider now returns the raw `.ics` text unparsed (design.md D11) —
parsing/filtering moved to `parse_ical_holidays(ics_text, city_code)`,
exercised separately in test_ical_holiday_parser.py.
"""

import httpx
import pytest

from mobility_manager.infrastructure.holiday_calendar.google_calendar_provider import (
    DEFAULT_HOLIDAY_ICAL_URL,
    GoogleCalendarHolidayProvider,
)

_VALID_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:1@test
DTSTART;VALUE=DATE:20260101
DTEND;VALUE=DATE:20260102
SUMMARY:Ano Nuevo
DESCRIPTION:Día festivo
END:VEVENT
END:VCALENDAR
"""


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Patch httpx.Client so every request is routed through `handler`."""
    transport = httpx.MockTransport(handler)
    original_client_cls = httpx.Client

    def _fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _fake_client)


# ---------------------------------------------------------------------------
# Hostname allowlist
# ---------------------------------------------------------------------------


def test_construction_accepts_default_url() -> None:
    GoogleCalendarHolidayProvider()


def test_construction_accepts_allowed_hostname() -> None:
    GoogleCalendarHolidayProvider(
        url="https://calendar.google.com/calendar/ical/other%40group.v.calendar.google.com/public/basic.ics"
    )


def test_construction_rejects_disallowed_hostname() -> None:
    with pytest.raises(ValueError, match="not in the allowed list"):
        GoogleCalendarHolidayProvider(url="https://evil.example.com/basic.ics")


# ---------------------------------------------------------------------------
# Configurable URL
# ---------------------------------------------------------------------------


def test_configurable_url_is_used_instead_of_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text=_VALID_ICS)

    _patch_client(monkeypatch, handler)
    override_url = "https://calendar.google.com/calendar/ical/override%40group.v.calendar.google.com/public/basic.ics"
    provider = GoogleCalendarHolidayProvider(url=override_url)

    provider.fetch_raw_calendar()

    assert str(captured["request"].url) == override_url
    assert override_url != DEFAULT_HOLIDAY_ICAL_URL


# ---------------------------------------------------------------------------
# fetch_raw_calendar()
# ---------------------------------------------------------------------------


def test_fetch_raw_calendar_returns_unparsed_text_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_VALID_ICS)

    _patch_client(monkeypatch, handler)
    provider = GoogleCalendarHolidayProvider()

    raw_calendar = provider.fetch_raw_calendar()

    assert raw_calendar == _VALID_ICS


def test_fetch_raw_calendar_sends_standard_browser_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text=_VALID_ICS)

    _patch_client(monkeypatch, handler)
    provider = GoogleCalendarHolidayProvider()

    provider.fetch_raw_calendar()

    assert "Mozilla" in captured["request"].headers["user-agent"]


def test_fetch_raw_calendar_raises_runtime_error_on_non_2xx_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    _patch_client(monkeypatch, handler)
    provider = GoogleCalendarHolidayProvider()

    with pytest.raises(RuntimeError, match="503"):
        provider.fetch_raw_calendar()


def test_fetch_raw_calendar_propagates_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    _patch_client(monkeypatch, handler)
    provider = GoogleCalendarHolidayProvider()

    with pytest.raises(httpx.ConnectTimeout):
        provider.fetch_raw_calendar()
