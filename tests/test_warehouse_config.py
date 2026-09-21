"""Protect database target selection, TLS, and secret-safe failures without a network."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.warehouse import __main__ as cli
from src.warehouse.config import WarehouseSettings, connect


@pytest.fixture
def values(tmp_path: Path) -> dict[str, object]:
    certificate = tmp_path / "ca.crt"
    certificate.write_text("public certificate placeholder")
    return {
        "environment": "development",
        "project_ref": "abcdefghijklmnopqrst",
        "host": "db.abcdefghijklmnopqrst.supabase.co",
        "user": "postgres",
        "password": "synthetic-password-not-a-credential",
        "sslrootcert": certificate,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("host", "db.wrongproject.supabase.co"),
        ("host", "db.abcdefghijklmnopqrst.supabase.co.attacker.invalid"),
        ("port", 6543),
        ("database", "unreviewed"),
        ("user", "unreviewed"),
        ("password", "REPLACE_ME"),
        ("password", ""),
    ],
)
def test_rejects_unsafe_target(values: dict[str, object], field: str, value: object) -> None:
    values[field] = value
    with pytest.raises(ValidationError):
        WarehouseSettings.model_validate(values)


def test_session_pooler_requires_project_username(values: dict[str, object]) -> None:
    values["host"] = "aws-0-ap-northeast-1.pooler.supabase.com"
    with pytest.raises(ValidationError):
        WarehouseSettings.model_validate(values)
    values["user"] = "postgres.abcdefghijklmnopqrst"
    settings = WarehouseSettings.model_validate(values)
    assert settings.port == 5432


def test_missing_certificate_fails_before_connect(values: dict[str, object]) -> None:
    values["sslrootcert"] = "missing-certificate.crt"
    with pytest.raises(ValueError, match="certificate"):
        connect(WarehouseSettings.model_validate(values))


def test_driver_always_verifies_server(
    values: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def capture(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("src.warehouse.config.psycopg.connect", capture)
    settings = WarehouseSettings.model_validate(values)
    connect(settings)
    assert captured["sslmode"] == "verify-full"
    assert captured["sslrootcert"] == str(values["sslrootcert"])
    assert captured["connect_timeout"] == 10
    assert str(values["password"]) not in repr(settings)


def test_cli_validation_never_prints_input_secrets(
    values: dict[str, object], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    values["host"] = values["password"]

    def invalid_settings() -> WarehouseSettings:
        return WarehouseSettings.model_validate(values)

    monkeypatch.setattr(cli, "load_settings", invalid_settings)
    monkeypatch.setattr("sys.argv", ["warehouse", "inspect"])
    assert cli.main() == 1
    output = capsys.readouterr()
    assert str(values["password"]) not in output.err + output.out
    assert "Invalid warehouse configuration" in output.err


def test_dotenv_parses_port_and_preserves_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.warehouse.config import load_settings

    for name in (
        "ENVIRONMENT",
        "PROJECT_REF",
        "HOST",
        "PORT",
        "DATABASE",
        "USER",
        "PASSWORD",
        "SSLROOTCERT",
    ):
        monkeypatch.delenv("WAREHOUSE_" + name, raising=False)
    (tmp_path / ".env.warehouse").write_text(
        "WAREHOUSE_ENVIRONMENT=development\n"
        "WAREHOUSE_PROJECT_REF=abcdefghijklmnopqrst\n"
        "WAREHOUSE_HOST=db.abcdefghijklmnopqrst.supabase.co\n"
        "WAREHOUSE_PORT=5432\nWAREHOUSE_DATABASE=postgres\nWAREHOUSE_USER=postgres\n"
        "WAREHOUSE_PASSWORD='synthetic @ # password'\nWAREHOUSE_SSLROOTCERT=ca.crt\n"
    )
    settings = load_settings(tmp_path)
    assert settings.port == 5432
    assert settings.password.get_secret_value() == "synthetic @ # password"
    monkeypatch.setenv("WAREHOUSE_ENVIRONMENT", "test")
    assert load_settings(tmp_path).environment == "test"
