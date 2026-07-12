"""
Unit tests for the shared shapefile-zip download/extraction helpers used by
both ser_band_shapefile.py and barrios_shapefile.py.

These cover the generic logic once here (hostname allowlist rejection,
successful zip fetch, missing-component-in-zip error); each of
test_ser_band_shapefile.py / test_barrios_shapefile.py additionally keeps a
thin test confirming it wires this shared helper with its own URL/basename.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from mobility_manager.infrastructure.parking_services.madrid.shapefile_zip import (
    extract_shapefile_components,
    fetch_zip,
    hostname_allowed,
)


def test_hostname_allowed_accepts_allowlisted_hostname() -> None:
    hostname_allowed("https://example.com/file.zip", {"example.com"})


def test_hostname_allowed_rejects_disallowed_hostname() -> None:
    with pytest.raises(ValueError, match="allowed list"):
        hostname_allowed("https://evil.example.com/file.zip", {"example.com"})


def test_fetch_zip_rejects_disallowed_hostname_before_any_network_call() -> None:
    with patch("httpx.Client") as mock_client_cls:
        with pytest.raises(ValueError, match="allowed list"):
            fetch_zip("https://evil.example.com/file.zip", {"example.com"}, source_label="test zip")

        mock_client_cls.assert_not_called()


def test_fetch_zip_returns_raw_bytes_on_success() -> None:
    response = MagicMock()
    response.is_success = True
    response.content = b"zip-bytes"

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = response

        content = fetch_zip("https://example.com/file.zip", {"example.com"}, source_label="test zip")

    assert content == b"zip-bytes"


def test_fetch_zip_raises_with_status_code_on_http_failure() -> None:
    response = MagicMock()
    response.is_success = False
    response.status_code = 503

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = response

        with pytest.raises(RuntimeError, match="503"):
            fetch_zip("https://example.com/file.zip", {"example.com"}, source_label="test zip")


def _build_zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_extract_shapefile_components_returns_shp_and_dbf_streams() -> None:
    zip_bytes = _build_zip({"FOO.shp": b"shp-bytes", "FOO.dbf": b"dbf-bytes"})

    shp_bytes, dbf_bytes = extract_shapefile_components(zip_bytes, "FOO", zip_label="Foo shapefile")

    assert shp_bytes.read() == b"shp-bytes"
    assert dbf_bytes.read() == b"dbf-bytes"


def test_extract_shapefile_components_is_case_insensitive_on_basename() -> None:
    zip_bytes = _build_zip({"path/foo.SHP": b"shp-bytes", "path/foo.DBF": b"dbf-bytes"})

    shp_bytes, dbf_bytes = extract_shapefile_components(zip_bytes, "FOO", zip_label="Foo shapefile")

    assert shp_bytes.read() == b"shp-bytes"
    assert dbf_bytes.read() == b"dbf-bytes"


def test_extract_shapefile_components_raises_when_component_missing() -> None:
    zip_bytes = _build_zip({"FOO.shp": b"shp-bytes"})  # .dbf missing

    with pytest.raises(RuntimeError, match="Foo shapefile zip did not contain FOO.shp/.dbf"):
        extract_shapefile_components(zip_bytes, "FOO", zip_label="Foo shapefile")
