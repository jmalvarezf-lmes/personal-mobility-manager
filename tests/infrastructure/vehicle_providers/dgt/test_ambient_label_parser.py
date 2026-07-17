"""
Unit tests for the DGT ambient label HTML parser.

Uses three captured real-response HTML shapes (found/B, confirmed-no-label/A,
not-found) saved as fixtures under tests/infrastructure/vehicle_providers/dgt/fixtures/.
"""

from pathlib import Path

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.infrastructure.vehicle_providers.dgt.ambient_label_parser import (
    parse_ambient_label_response,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_success_container_resolves_label_b() -> None:
    html = _load_fixture("found_b.html")
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.FOUND
    assert result.label == AmbientLabel.B


def test_success_container_extracts_icon_relative_url() -> None:
    html = _load_fixture("found_b.html")
    result = parse_ambient_label_response(html)
    assert result.icon_relative_url is not None
    assert "distintivo_B_sin_fondo.svg" in result.icon_relative_url


def test_warning_container_resolves_confirmed_no_label() -> None:
    html = _load_fixture("confirmed_no_label.html")
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.FOUND
    assert result.label == AmbientLabel.A
    assert result.icon_relative_url is None


def test_danger_container_resolves_not_found() -> None:
    html = _load_fixture("not_found.html")
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.NOT_FOUND
    assert result.label is None


def test_cross_check_mismatch_resolves_error() -> None:
    html = """
    <div class="border rounded border-success p-4">
      <img src="/images/distintivo_B_sin_fondo.svg">
      <strong>Distintivo Ambiental C.</strong>
    </div>
    """
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.ERROR
    assert result.label is None


def test_success_container_missing_text_resolves_error() -> None:
    html = """
    <div class="border rounded border-success p-4">
      <img src="/images/distintivo_B_sin_fondo.svg">
    </div>
    """
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.ERROR


def test_unrecognized_shape_resolves_error() -> None:
    html = "<div class='some-other-container'>Unexpected content</div>"
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.ERROR
    assert result.label is None


def test_success_container_resolves_zero_label() -> None:
    html = """
    <div class="border rounded border-success p-4">
      <img src="/images/distintivo_0_sin_fondo.svg">
      <strong>Distintivo Ambiental 0.</strong>
    </div>
    """
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.FOUND
    assert result.label == AmbientLabel.ZERO


def test_success_container_resolves_eco_label() -> None:
    html = """
    <div class="border rounded border-success p-4">
      <img src="/images/distintivo_ECO_sin_fondo.svg">
      <strong>Distintivo Ambiental ECO.</strong>
    </div>
    """
    result = parse_ambient_label_response(html)
    assert result.status == AmbientLabelStatus.FOUND
    assert result.label == AmbientLabel.ECO
