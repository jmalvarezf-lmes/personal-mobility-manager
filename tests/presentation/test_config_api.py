"""
Presentation tests for GET /config endpoint.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.presentation.api.routers.config import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_config_returns_none_when_osm_tile_url_not_set(monkeypatch) -> None:
    monkeypatch.delenv("OSM_TILE_URL", raising=False)
    client = TestClient(_build_app())

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {"osm_tile_url": None}


def test_config_returns_url_when_osm_tile_url_is_set(monkeypatch) -> None:
    tile_url = "http://tiles.local:8080/tile/{z}/{x}/{y}.png"
    monkeypatch.setenv("OSM_TILE_URL", tile_url)
    client = TestClient(_build_app())

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {"osm_tile_url": tile_url}
