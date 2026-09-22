"""Offline checks for dbt credential isolation, schema boundaries, and real parsing."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.validation.contracts import TABLES
from src.warehouse import dbt_runner
from src.warehouse.config import WarehouseSettings

PROJECT = Path(__file__).resolve().parents[1] / "dbt"


@pytest.fixture
def dbt_root(tmp_path: Path) -> Path:
    shutil.copytree(PROJECT, tmp_path / "dbt", ignore=shutil.ignore_patterns("target", "logs"))
    return tmp_path


@pytest.fixture
def transformer_settings(tmp_path: Path) -> WarehouseSettings:
    certificate = tmp_path / "ca.crt"
    certificate.write_text("synthetic public certificate placeholder", encoding="utf-8")
    return WarehouseSettings.model_validate(
        {
            "purpose": "transformer",
            "environment": "test",
            "project_ref": "abcdefghijklmnopqrst",
            "host": "db.abcdefghijklmnopqrst.supabase.co",
            "user": "commercelens_transform",
            "password": "synthetic-dbt-password-do-not-print",
            "sslrootcert": certificate,
        }
    )


def test_parse_never_loads_private_settings_and_overrides_ambient_configuration(
    dbt_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def forbid_settings(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline parsing must not read private configuration")

    def capture(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured.update(args=args, **kwargs)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(dbt_runner, "load_settings", forbid_settings)
    monkeypatch.setattr(dbt_runner.subprocess, "run", capture)
    for name in (
        "WAREHOUSE_PASSWORD",
        "DBT_ENV_SECRET_UNRELATED",
        "DBT_PROFILES_DIR",
        "DBT_LOG_LEVEL",
        "PGPASSWORD",
        "PGSERVICEFILE",
    ):
        monkeypatch.setenv(name, "ambient-sensitive-value")
    result = dbt_runner.run_dbt("parse", dbt_root)
    assert result["offline"] is True
    environment = captured["env"]
    assert "ambient-sensitive-value" not in environment.values()
    assert environment["DBT_ENV_SECRET_WAREHOUSE_USER"] == "commercelens_transform"
    assert environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] == "false"
    args = captured["args"]
    assert args[args.index("--profiles-dir") + 1] == str(dbt_root / "dbt/profiles")
    assert args[args.index("--project-dir") + 1] == str(dbt_root / "dbt")
    assert "--no-partial-parse" in args
    assert captured["stdout"] == captured["stderr"] == subprocess.DEVNULL
    assert captured["timeout"] == 120


def test_debug_uses_only_transformer_profile_and_secret_environment(
    dbt_root: Path,
    transformer_settings: WarehouseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def settings(root: Path, *, purpose: str) -> WarehouseSettings:
        assert root == dbt_root
        assert purpose == "transformer"
        return transformer_settings

    def capture(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured.update(args=args, **kwargs)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(dbt_runner, "load_settings", settings)
    monkeypatch.setattr(dbt_runner.subprocess, "run", capture)
    assert dbt_runner.run_dbt("debug", dbt_root)["offline"] is False
    secret = transformer_settings.password.get_secret_value()
    assert secret not in repr(captured["args"])
    assert captured["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] == secret
    assert captured["env"]["DBT_ENV_SECRET_WAREHOUSE_SSLROOTCERT"] == str(
        transformer_settings.certificate_path()
    )


@pytest.mark.parametrize("failure", ["returncode", "timeout", "oserror"])
def test_subprocess_failures_never_reveal_password_or_driver_output(
    dbt_root: Path,
    transformer_settings: WarehouseSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    secret = transformer_settings.password.get_secret_value()
    monkeypatch.setattr(dbt_runner, "load_settings", lambda *a, **kw: transformer_settings)

    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 120, output=secret, stderr=secret)
        if failure == "oserror":
            raise OSError(secret)
        return subprocess.CompletedProcess(args, 2, stdout=secret, stderr=secret)

    monkeypatch.setattr(dbt_runner.subprocess, "run", fail)
    with pytest.raises(dbt_runner.DbtError) as error:
        dbt_runner.run_dbt("debug", dbt_root)
    output = capsys.readouterr()
    assert secret not in str(error.value) + output.out + output.err
    assert error.value.__suppress_context__ or failure == "returncode"


def test_debug_requires_ca_before_starting_subprocess(
    dbt_root: Path, transformer_settings: WarehouseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    transformer_settings.sslrootcert = dbt_root / "missing.crt"
    monkeypatch.setattr(dbt_runner, "load_settings", lambda *a, **kw: transformer_settings)
    monkeypatch.setattr(
        dbt_runner.subprocess,
        "run",
        lambda *a, **kw: pytest.fail("Missing certificate must fail before launching dbt"),
    )
    with pytest.raises(ValueError, match="certificate"):
        dbt_runner.run_dbt("debug", dbt_root)


def test_debug_rejects_admin_settings_before_starting_subprocess(
    dbt_root: Path, transformer_settings: WarehouseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = transformer_settings.model_copy(update={"purpose": "admin", "user": "postgres"})
    monkeypatch.setattr(dbt_runner, "load_settings", lambda *a, **kw: admin)
    monkeypatch.setattr(
        dbt_runner.subprocess,
        "run",
        lambda *a, **kw: pytest.fail("Administrator settings must not launch dbt"),
    )
    with pytest.raises(dbt_runner.DbtError, match="dedicated transformer"):
        dbt_runner.run_dbt("debug", dbt_root)


def test_rejects_unapproved_command_before_reading_settings(dbt_root: Path) -> None:
    with pytest.raises(dbt_runner.DbtError, match="Only dbt parse and debug"):
        dbt_runner.run_dbt("build", dbt_root)  # type: ignore[arg-type]


def test_tracked_profile_has_verified_tls_role_and_only_secret_references() -> None:
    yaml = pytest.importorskip("yaml")
    profile = yaml.safe_load((PROJECT / "profiles/profiles.yml").read_text(encoding="utf-8"))
    target = profile["commercelens"]["outputs"]["development"]
    assert target["role"] == "commercelens_transformer"
    assert target["sslmode"] == "verify-full"
    assert target["threads"] == 1
    for name in ("host", "user", "password", "sslrootcert"):
        assert target[name] == "{{ env_var('DBT_ENV_SECRET_WAREHOUSE_" + name.upper() + "') }}"


@pytest.mark.parametrize("schema", [None, "staging", "core", "marts", " core "])
def test_schema_macro_uses_exact_existing_schema(schema: str | None) -> None:
    result = render_schema(schema, "staging")
    assert result == ("staging" if schema is None else schema.strip())


@pytest.mark.parametrize("schema", ["raw", "ops", "public", "staging_core", "", "CORE"])
def test_schema_macro_rejects_unapproved_custom_schema(schema: str) -> None:
    with pytest.raises(ValueError, match="model schema is not approved"):
        render_schema(schema, "staging")


def test_schema_macro_rejects_unapproved_target_even_with_approved_custom_schema() -> None:
    with pytest.raises(ValueError, match="target schema is not approved"):
        render_schema("core", "public")


def render_schema(custom: str | None, target: str) -> str:
    def reject(message: str) -> None:
        raise ValueError(message)

    template = (
        pytest.importorskip("jinja2")
        .Environment()
        .from_string((PROJECT / "macros/generate_schema_name.sql").read_text(encoding="utf-8"))
    )
    module = template.make_module(
        {"target": {"schema": target}, "exceptions": SimpleNamespace(raise_compiler_error=reject)}
    )
    return module.generate_schema_name(custom, {}).strip()


def test_real_dbt_parse_without_network_preserves_sources_and_schema_boundaries(
    dbt_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("dbt.cli.main")
    pytest.importorskip("psycopg2")
    # Temporary models exercise the real dbt macro integration; none are shipped.
    for schema in ("staging", "core", "marts"):
        (dbt_root / f"dbt/models/probe_{schema}.sql").write_text(
            "{{ config(schema='" + schema + "') }} select 1 as probe", encoding="utf-8"
        )
    network_marker = dbt_root / "network-attempt.txt"
    actual_run = subprocess.run
    guard = (
        "import pathlib, runpy, socket, sys, psycopg2\n"
        f"marker = pathlib.Path({str(network_marker)!r})\n"
        "def forbidden(*args, **kwargs):\n"
        "    marker.write_text('attempted')\n"
        "    raise RuntimeError('Network is forbidden in the offline parse test')\n"
        "socket.socket.connect = forbidden\n"
        "socket.create_connection = forbidden\n"
        "psycopg2.connect = forbidden\n"
        "sys.argv[0] = 'dbt'\n"
        "runpy.run_module('dbt.cli.main', run_name='__main__')\n"
    )

    def guarded_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert args[1:4] == ["-I", "-m", "dbt.cli.main"]
        return actual_run([args[0], "-I", "-c", guard, *args[4:]], **kwargs)

    monkeypatch.setattr(dbt_runner.subprocess, "run", guarded_run)
    assert dbt_runner.run_dbt("parse", dbt_root)["status"] == "passed"
    assert not network_marker.exists()
    manifest = json.loads((dbt_root / "dbt/target/manifest.json").read_text(encoding="utf-8"))
    sources = {source["name"]: source for source in manifest["sources"].values()}
    assert set(sources) == set(TABLES)
    for name, contract in TABLES.items():
        source = sources[name]
        assert source["schema"] == "raw"
        assert set(source["columns"]) == {"_load_id", "_source_row", *contract.columns}
        assert all(source["columns"][column]["data_type"] == "text" for column in contract.columns)
    for node in manifest["nodes"].values():
        assert node["schema"] == node["name"].removeprefix("probe_")
        assert node["config"]["materialized"] == "view"
    # Check every generated artifact, not just the public manifest.
    secret = b"offline-parse-synthetic-password"
    for path in (dbt_root / "dbt").rglob("*"):
        if path.is_file():
            assert secret not in path.read_bytes(), path.name
    (dbt_root / "dbt/models/forbidden.sql").write_text(
        "{{ config(schema='raw') }} select 1 as probe", encoding="utf-8"
    )
    with pytest.raises(dbt_runner.DbtError, match="dbt parse failed"):
        dbt_runner.run_dbt("parse", dbt_root)
    assert not network_marker.exists()


def test_real_debug_attempts_verified_connection_and_propagates_failure_safely(
    dbt_root: Path,
    transformer_settings: WarehouseSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pytest.importorskip("dbt.cli.main")
    pytest.importorskip("psycopg2")
    marker = dbt_root / "guarded-connection.json"
    actual_run = subprocess.run
    guard = (
        "import json, pathlib, runpy, socket, sys, psycopg2\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "def forbidden(*args, **kwargs):\n"
        "    raise RuntimeError('Network is forbidden in this test')\n"
        "def connection(*args, **kwargs):\n"
        "    marker.write_text(json.dumps({\n"
        "        'verify_full': kwargs.get('sslmode') == 'verify-full',\n"
        "        'dedicated_login': kwargs.get('user') == 'commercelens_transform',\n"
        "        'ca_present': bool(kwargs.get('sslrootcert')),\n"
        "        'connect_timeout': kwargs.get('connect_timeout')}))\n"
        "    raise psycopg2.OperationalError(kwargs['password'])\n"
        "socket.socket.connect = forbidden\n"
        "socket.create_connection = forbidden\n"
        "psycopg2.connect = connection\n"
        "sys.argv[0] = 'dbt'\n"
        "runpy.run_module('dbt.cli.main', run_name='__main__')\n"
    )

    def guarded_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return actual_run([args[0], "-I", "-c", guard, *args[4:]], **kwargs)

    monkeypatch.setattr(dbt_runner, "load_settings", lambda *a, **kw: transformer_settings)
    monkeypatch.setattr(dbt_runner.subprocess, "run", guarded_run)
    with pytest.raises(dbt_runner.DbtError, match="dbt debug failed") as error:
        dbt_runner.run_dbt("debug", dbt_root)
    assert json.loads(marker.read_text()) == {
        "verify_full": True,
        "dedicated_login": True,
        "ca_present": True,
        "connect_timeout": 10,
    }
    secret = transformer_settings.password.get_secret_value()
    output = capsys.readouterr()
    assert secret not in str(error.value) + output.out + output.err
    for path in (dbt_root / "dbt").rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes(), path.name
