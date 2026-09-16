"""Verify the public foundation contract and configuration failure behavior."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app.config import Settings
from api.app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(environment="test", _env_file=None))) as test_client:
        yield test_client


def test_health_contract(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "commercelens-api"}


def test_openapi_documents_health_response(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CommerceLens API"
    response_schema = schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema["$ref"].endswith("/HealthResponse")
    assert client.get("/docs").status_code == 200


def test_unknown_route_returns_404(client):
    assert client.get("/api/v1/kpis").status_code == 404


def test_environment_variable_overrides_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("COMMERCE_ENVIRONMENT=development\n", encoding="utf-8")
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "test")
    assert Settings(_env_file=env_file).environment == "test"


def test_invalid_environment_fails_fast(monkeypatch):
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "typo")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
