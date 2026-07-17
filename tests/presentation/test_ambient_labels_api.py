"""
Presentation tests for GET /ambient-labels/{label}/icon.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.ports.ambient_label_icon_repository import (
    AmbientLabelIcon,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.presentation.api.routers.ambient_labels import router


def _build_app(icon_repo=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if icon_repo is not None:
        app.state.ambient_label_icon_repo = icon_repo
    return app


def test_cached_label_returns_200_with_bytes_and_content_type() -> None:
    icon_repo = MagicMock()
    icon_repo.get_by_label.return_value = AmbientLabelIcon(image_bytes=b"fake-svg", content_type="image/svg+xml")
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/B/icon")

    assert response.status_code == 200
    assert response.content == b"fake-svg"
    assert response.headers["content-type"] == "image/svg+xml"
    icon_repo.get_by_label.assert_called_once_with(AmbientLabel.B)


def test_cached_label_sets_long_lived_cache_control() -> None:
    icon_repo = MagicMock()
    icon_repo.get_by_label.return_value = AmbientLabelIcon(image_bytes=b"fake-svg", content_type="image/svg+xml")
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/C/icon")

    assert "max-age" in response.headers["cache-control"]


def test_label_a_returns_404_without_querying_cache() -> None:
    icon_repo = MagicMock()
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/A/icon")

    assert response.status_code == 404
    icon_repo.get_by_label.assert_not_called()


def test_uncached_label_returns_404() -> None:
    icon_repo = MagicMock()
    icon_repo.get_by_label.return_value = None
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/ECO/icon")

    assert response.status_code == 404


def test_unknown_label_string_returns_404() -> None:
    icon_repo = MagicMock()
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/bmw/icon")

    assert response.status_code == 404
    icon_repo.get_by_label.assert_not_called()


def test_zero_label_is_addressable_via_url_path() -> None:
    icon_repo = MagicMock()
    icon_repo.get_by_label.return_value = AmbientLabelIcon(image_bytes=b"zero-svg", content_type="image/svg+xml")
    client = TestClient(_build_app(icon_repo=icon_repo))

    response = client.get("/ambient-labels/0/icon")

    assert response.status_code == 200
    icon_repo.get_by_label.assert_called_once_with(AmbientLabel.ZERO)
