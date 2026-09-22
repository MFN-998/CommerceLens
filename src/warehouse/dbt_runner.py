"""Narrow dbt setup commands with explicit paths and no sensitive diagnostics."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from src.warehouse.config import ROOT, WarehouseSettings, load_settings

DbtCommand = Literal["parse", "debug"]


class DbtError(ValueError):
    """Fixed, safe diagnostics; never expose a subprocess or connection exception."""


def _parse_settings() -> WarehouseSettings:
    """Supply every setting without opening a private file or connecting to a target."""
    return WarehouseSettings.model_validate(
        {
            "purpose": "transformer",
            "environment": "test",
            "project_ref": "abcdefghijklmnopqrst",
            "host": "db.abcdefghijklmnopqrst.supabase.co",
            "port": 5432,
            "database": "postgres",
            "user": "commercelens_transform",
            "password": "offline-parse-synthetic-password",
            # dbt parse does not open a connection or inspect this certificate.
            "sslrootcert": Path("offline-parse-unused-ca.crt"),
        }
    )


def _environment(settings: WarehouseSettings, certificate: Path) -> dict[str, str]:
    # Do not let global dbt flags, libpq defaults, or unrelated warehouse secrets
    # cross the process boundary. Retain normal OS runtime variables (Windows too).
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(("DBT_", "WAREHOUSE_", "PG"))
    }
    environment.update(
        DBT_ENV_SECRET_WAREHOUSE_HOST=settings.host,
        DBT_ENV_SECRET_WAREHOUSE_USER=settings.user,
        DBT_ENV_SECRET_WAREHOUSE_PASSWORD=settings.password.get_secret_value(),
        DBT_ENV_SECRET_WAREHOUSE_SSLROOTCERT=str(certificate),
        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
        DO_NOT_TRACK="1",
        PGOPTIONS="-c statement_timeout=60000 -c lock_timeout=10000 "
        "-c idle_in_transaction_session_timeout=60000",
    )
    return environment


def run_dbt(command: DbtCommand, root: Path = ROOT) -> dict[str, str | bool]:
    """Parse offline, or debug the dedicated transformer login with verified TLS.

    Run only the current Python environment's pinned dbt installation. Output is
    discarded, not captured in memory or printed; dbt file logging is disabled.
    Secret-prefixed profile variables additionally enable dbt's own redaction.
    """
    if command not in ("parse", "debug"):
        raise DbtError("Only dbt parse and debug are available in the setup milestone")
    root = root.resolve()
    project = root / "dbt"
    profiles = project / "profiles"
    if not (project / "dbt_project.yml").is_file() or not (profiles / "profiles.yml").is_file():
        raise DbtError("The tracked dbt project or profile is missing")
    settings = (
        _parse_settings() if command == "parse" else load_settings(root, purpose="transformer")
    )
    if settings.purpose != "transformer":
        raise DbtError("dbt requires the dedicated transformer configuration")
    certificate = settings.sslrootcert if command == "parse" else settings.certificate_path(root)
    args = [
        sys.executable,
        "-I",
        "-m",
        "dbt.cli.main",
        command,
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(profiles),
        "--profile",
        "commercelens",
        "--target",
        "development",
        "--no-send-anonymous-usage-stats",
        "--no-partial-parse",
        "--log-level",
        "none",
        "--log-level-file",
        "none",
        "--log-path",
        str(project / "logs"),
    ]
    if command == "parse":
        args.extend(["--target-path", str(project / "target")])
    try:
        result = subprocess.run(
            args,
            cwd=root,
            env=_environment(settings, certificate),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DbtError(
            "dbt setup command exceeded its two-minute limit; no detail logged"
        ) from None
    except OSError:
        raise DbtError(
            "dbt could not start in the current Python environment; no detail logged"
        ) from None
    if result.returncode != 0:
        raise DbtError(
            f"dbt {command} failed (exit {result.returncode}); check the locked transform "
            "environment and project/configuration. Subprocess detail was not logged."
        )
    return {"command": f"dbt-{command}", "status": "passed", "offline": command == "parse"}
