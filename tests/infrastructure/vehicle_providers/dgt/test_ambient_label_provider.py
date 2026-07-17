"""
Unit tests for DgtAmbientLabelProvider.

HTTP calls are exercised via httpx.MockTransport so tests run without any
real network access, following the same pattern as
tests/infrastructure/test_elparking_provider.py.
"""

import httpx
import pytest

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.infrastructure.vehicle_providers.dgt.ambient_label_provider import (
    DgtAmbientLabelProvider,
)

_BASE_URL = "https://sede.dgt.gob.es/dgt-nuevo/distintivo-ambiental/index.html"


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Patch httpx.Client so every request is routed through `handler`."""
    transport = httpx.MockTransport(handler)
    original_client_cls = httpx.Client

    def _fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _fake_client)


# ---------------------------------------------------------------------------
# Hostname validation
# ---------------------------------------------------------------------------


def test_construction_accepts_allowed_hostname() -> None:
    DgtAmbientLabelProvider(url=_BASE_URL)


def test_construction_rejects_disallowed_hostname() -> None:
    with pytest.raises(ValueError, match="not in the allowed list"):
        DgtAmbientLabelProvider(url="https://evil.example.com/index.html")


# ---------------------------------------------------------------------------
# lookup()
# ---------------------------------------------------------------------------


def test_lookup_sends_plate_as_query_param(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text="<div class='alert alert-danger'>No se ha encontrado</div>")

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    provider.lookup("1234ABC")

    request = captured["request"]
    assert request.url.params["matricula"] == "1234ABC"


def test_lookup_sends_standard_browser_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, text="<div class='alert alert-danger'>No se ha encontrado</div>")

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    provider.lookup("1234ABC")

    user_agent = captured["request"].headers["user-agent"]
    assert "Mozilla" in user_agent
    assert "dgt" not in user_agent.lower()


def test_lookup_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                '<div class="border rounded border-success">'
                '<img src="/images/distintivo_B_sin_fondo.svg">'
                "<strong>Distintivo Ambiental B.</strong>"
                "</div>"
            ),
        )

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    result = provider.lookup("1234ABC")

    assert result.status == AmbientLabelStatus.FOUND
    assert result.label == AmbientLabel.B


def test_lookup_raises_on_non_2xx_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    with pytest.raises(RuntimeError, match="503"):
        provider.lookup("1234ABC")


def test_lookup_propagates_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    with pytest.raises(httpx.ConnectTimeout):
        provider.lookup("1234ABC")


# ---------------------------------------------------------------------------
# download_icon()
# ---------------------------------------------------------------------------


def test_download_icon_resolves_relative_url_against_allowed_host(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, content=b"fake-svg-bytes", headers={"content-type": "image/svg+xml"})

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    image_bytes, content_type = provider.download_icon("/dgt-nuevo/images/distintivos/distintivo_B_sin_fondo.svg")

    assert image_bytes == b"fake-svg-bytes"
    assert content_type == "image/svg+xml"
    assert captured["request"].url.host == "sede.dgt.gob.es"


def test_download_icon_rejects_disallowed_resolved_host() -> None:
    provider = DgtAmbientLabelProvider(url=_BASE_URL)
    with pytest.raises(ValueError, match="not in the allowed list"):
        provider.download_icon("https://evil.example.com/distintivo_B_sin_fondo.svg")


def test_download_icon_raises_on_non_2xx_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    _patch_client(monkeypatch, handler)
    provider = DgtAmbientLabelProvider(url=_BASE_URL)

    with pytest.raises(RuntimeError, match="404"):
        provider.download_icon("/dgt-nuevo/images/distintivos/distintivo_B_sin_fondo.svg")
