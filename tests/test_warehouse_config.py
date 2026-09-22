"""Protect database target selection, TLS, and secret-safe failures without a network."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.warehouse import __main__ as cli
from src.warehouse.config import (
    PURPOSE_FILES,
    PURPOSE_USERS,
    WarehouseSettings,
    connect,
    load_settings,
)


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
    for name in (
        "PURPOSE",
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


@pytest.mark.parametrize("pooler", [False, True])
@pytest.mark.parametrize("purpose", ["loader", "transformer"])
def test_restricted_target_requires_matching_identity(values, pooler, purpose) -> None:
    values["purpose"] = purpose
    if pooler:
        values["host"] = "aws-0-ap-northeast-1.pooler.supabase.com"
        values["user"] = "postgres.abcdefghijklmnopqrst"
    with pytest.raises(ValidationError):
        WarehouseSettings.model_validate(values)
    values["user"] = PURPOSE_USERS[purpose] + (".abcdefghijklmnopqrst" if pooler else "")
    assert WarehouseSettings.model_validate(values).purpose == purpose
    values["purpose"] = "admin"
    with pytest.raises(ValidationError):
        WarehouseSettings.model_validate(values)


@pytest.fixture
def clean_warehouse_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for name in os.environ:
        if name.startswith("WAREHOUSE_"):
            monkeypatch.delenv(name)


def write_config(path: Path, purpose: str, user: str) -> None:
    path.write_text(
        f"WAREHOUSE_PURPOSE={purpose}\n"
        "WAREHOUSE_ENVIRONMENT=test\n"
        "WAREHOUSE_PROJECT_REF=abcdefghijklmnopqrst\n"
        "WAREHOUSE_HOST=db.abcdefghijklmnopqrst.supabase.co\n"
        f"WAREHOUSE_USER={user}\n"
        "WAREHOUSE_PASSWORD=synthetic-test-only-password\n"
        "WAREHOUSE_SSLROOTCERT=ca.crt\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("purpose", ["loader", "transformer"])
def test_missing_restricted_file_never_uses_admin_file(
    tmp_path, clean_warehouse_environment, purpose
) -> None:
    write_config(tmp_path / ".env.warehouse", "admin", "postgres")
    assert load_settings(tmp_path).purpose == "admin"
    with pytest.raises(ValidationError):
        load_settings(tmp_path, purpose=purpose)


def test_each_command_uses_its_own_file(tmp_path, clean_warehouse_environment) -> None:
    write_config(tmp_path / ".env.warehouse", "admin", "postgres")
    write_config(tmp_path / ".env.warehouse.loader", "loader", "commercelens_ingest")
    write_config(tmp_path / ".env.warehouse.transformer", "transformer", "commercelens_transform")
    assert load_settings(tmp_path).user == "postgres"
    assert load_settings(tmp_path, purpose="loader").user == "commercelens_ingest"
    assert load_settings(tmp_path, purpose="transformer").user == "commercelens_transform"


@pytest.mark.parametrize("purpose", ["loader", "transformer"])
def test_restricted_purpose_rejects_ambient_admin_override(
    tmp_path, clean_warehouse_environment, monkeypatch, purpose
) -> None:
    write_config(tmp_path / PURPOSE_FILES[purpose], purpose, PURPOSE_USERS[purpose])
    monkeypatch.setenv("WAREHOUSE_USER", "postgres")
    with pytest.raises(ValidationError):
        load_settings(tmp_path, purpose=purpose)
    monkeypatch.setenv("WAREHOUSE_PURPOSE", "admin")
    with pytest.raises(ValueError, match="purpose does not match"):
        load_settings(tmp_path, purpose=purpose)


@pytest.mark.parametrize("purpose", ["admin", "loader", "transformer"])
def test_misplaced_configuration_is_rejected(tmp_path, clean_warehouse_environment, purpose):
    filename = PURPOSE_FILES[purpose]
    wrong_purpose, user = (
        ("loader", "commercelens_ingest") if purpose == "admin" else ("admin", "postgres")
    )
    write_config(tmp_path / filename, wrong_purpose, user)
    with pytest.raises(ValueError, match="purpose does not match"):
        load_settings(tmp_path, purpose=purpose)


@pytest.mark.parametrize("purpose", ["loader", "transformer"])
def test_restricted_connection_preserves_tls_and_marks_application(
    values, monkeypatch, purpose
) -> None:
    captured = {}
    monkeypatch.setattr("src.warehouse.config.psycopg.connect", lambda **kw: captured.update(kw))
    values.update(purpose=purpose, user=PURPOSE_USERS[purpose])
    connect(WarehouseSettings.model_validate(values))
    assert captured["sslmode"] == "verify-full"
    assert captured["user"] == PURPOSE_USERS[purpose]
    assert captured["application_name"] == f"commercelens-warehouse-{purpose}"


@pytest.mark.parametrize("purpose", ["loader", "transformer"])
def test_restricted_purposes_cannot_use_each_others_credentials(
    tmp_path, clean_warehouse_environment, purpose
):
    other = "transformer" if purpose == "loader" else "loader"
    write_config(tmp_path / PURPOSE_FILES[purpose], purpose, PURPOSE_USERS[other])
    with pytest.raises(ValidationError):
        load_settings(tmp_path, purpose=purpose)
