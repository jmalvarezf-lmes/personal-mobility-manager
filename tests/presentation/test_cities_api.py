"""
Presentation tests for GET /cities endpoint.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.city import City
from mobility_manager.presentation.api.routers.cities import router


def _build_app(repo_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.city_repo = repo_mock
    return app


def _make_repo(cities: list[City] | None = None) -> MagicMock:
    repo = MagicMock()
    repo.list_all.return_value = cities if cities is not None else []
    return repo


def test_list_cities_empty_returns_200_with_empty_list() -> None:
    repo = _make_repo()
    client = TestClient(_build_app(repo))

    response = client.get("/cities")

    assert response.status_code == 200
    assert response.json() == []


def test_list_cities_populated_returns_all_rows() -> None:
    repo = _make_repo(cities=[City(code="madrid", name="Madrid"), City(code="barcelona", name="Barcelona")])
    client = TestClient(_build_app(repo))

    response = client.get("/cities")

    assert response.status_code == 200
    data = response.json()
    assert data == [
        {"code": "madrid", "name": "Madrid"},
        {"code": "barcelona", "name": "Barcelona"},
    ]


def test_list_cities_requires_no_authentication() -> None:
    """No auth dependency is used on this router — a bare TestClient request must succeed."""
    repo = _make_repo(cities=[City(code="madrid", name="Madrid")])
    client = TestClient(_build_app(repo))

    response = client.get("/cities")

    assert response.status_code == 200
