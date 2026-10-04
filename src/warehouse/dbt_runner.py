"""Narrow dbt commands with explicit paths and no sensitive diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal
from uuid import uuid4

from src.warehouse.config import ROOT, WarehouseSettings, load_settings

DbtCommand = Literal["parse", "debug", "build", "test"]
APPROVED_MODELS = frozenset(
    {
        "stg_customers",
        "stg_sellers",
        "stg_category_translation",
        "stg_products",
        "stg_orders",
        "stg_order_items",
        "stg_order_payments",
        "stg_order_reviews",
        "stg_geolocation",
        "dim_location",
        "dim_seller",
        "dim_customer",
        "dim_product",
        "dim_date",
        "int_order_customers",
        "fact_orders",
    }
)


SETUP_TIMEOUT_SECONDS = 120
MODEL_JOB_TIMEOUT_SECONDS = 180


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


def run_dbt(
    command: DbtCommand, root: Path = ROOT, *, select: str | None = None
) -> dict[str, str | bool]:
    """Parse offline, or connect using the dedicated transformer login with verified TLS.

    Run only the current Python environment's pinned dbt installation. Output is
    discarded, not captured in memory or printed; dbt file logging is disabled.
    Secret-prefixed profile variables additionally enable dbt's own redaction.
    """
    if command not in ("parse", "debug", "build", "test"):
        raise DbtError("Unsupported dbt command")
    if command in ("build", "test"):
        if select not in APPROVED_MODELS:
            raise DbtError("Choose exactly one approved model for dbt build/test")
    elif select is not None:
        raise DbtError("Model selection is only supported for dbt build/test")
    timeout_seconds = (
        MODEL_JOB_TIMEOUT_SECONDS if command in ("build", "test") else SETUP_TIMEOUT_SECONDS
    )
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
    # Retain each invocation's outputs; never clear an earlier target or log directory.
    artifacts = root / ".artifacts" / "dbt" / uuid4().hex
    artifacts.mkdir(parents=True, exist_ok=False)
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
        "--no-use-v2-parser",
        "--log-level",
        "none",
        "--log-level-file",
        "none",
        "--log-path",
        str(artifacts / "logs"),
    ]
    if command != "debug":
        args.extend(["--target-path", str(artifacts / "target")])
    if select is not None:
        args.extend(["--select", select, "--indirect-selection", "eager"])
    try:
        result = subprocess.run(
            args,
            cwd=root,
            env=_environment(settings, certificate),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DbtError(
            f"dbt {command} exceeded its {timeout_seconds}-second limit; no detail logged"
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
    if command in ("build", "test"):
        _verify_model_results(artifacts / "target", command, str(select))
    return {
        "command": f"dbt-{command}",
        "status": "passed",
        "offline": command == "parse",
        "artifacts": str(artifacts.relative_to(root)),
    }


def _verify_model_results(target: Path, command: str, select: str) -> None:
    """A zero-exit empty selection is not a successful model/test milestone."""
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        results = json.loads((target / "run_results.json").read_text(encoding="utf-8"))["results"]
        model_id = f"model.commercelens.{select}"
        model = manifest["nodes"][model_id]
        if not model["config"]["enabled"] or model["config"]["materialized"] != "view":
            raise ValueError
        expected = {
            key: "pass"
            for key, node in manifest["nodes"].items()
            if node["resource_type"] == "test"
            and model_id in node["depends_on"]["nodes"]
            and node["config"]["enabled"]
        }
        if not expected:
            raise ValueError
        if command == "build":
            expected[model_id] = "success"
        actual = {item["unique_id"]: item["status"] for item in results}
        if len(actual) != len(results) or actual != expected:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise DbtError(
            "dbt did not verify the complete selected view/test results; artifacts retained"
        ) from None
