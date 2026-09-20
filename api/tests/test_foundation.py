"""Verify the public foundation contract and configuration failure behavior."""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app.config import Settings
from api.app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(environment="test", _env_file=None))) as test_client:
        yield test_client


def test_health_contract(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "commercelens-api"}


def test_openapi_documents_health_response(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CommerceLens API"
    response_schema = schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema["$ref"].endswith("/HealthResponse")
    assert client.get("/docs").status_code == 200


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/kpis").status_code == 404


def test_environment_variable_overrides_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("COMMERCE_ENVIRONMENT=development\n", encoding="utf-8")
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "test")
    assert Settings(_env_file=env_file).environment == "test"


def test_invalid_environment_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "typo")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_module_import_does_not_load_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tooling can import the application without consuming the developer's .env."""
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "invalid-import-sentinel")
    result = subprocess.run(
        [sys.executable, "-c", "import api.app.main"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_factory_validates_configuration_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "invalid-startup-sentinel")
    with pytest.raises(ValidationError):
        create_app()


def test_explicit_settings_isolate_application_from_ambient_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(environment="test", _env_file=None)
    monkeypatch.setenv("COMMERCE_ENVIRONMENT", "invalid-ambient-sentinel")
    application = create_app(settings)
    assert application.state.settings is settings
    with TestClient(application) as test_client:
        assert test_client.get("/health").status_code == 200
