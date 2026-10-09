"""Fixed full-graph jobs for an explicitly approved, isolated test warehouse.

The 1200-second job budget passed dated fresh-target verification on 2026-10-05;
see docs/warehouse-reconstruction-verification.json, not a duration guarantee.
Build failures may leave committed views; reconnect and inspect before retrying.
This callable does not provision a target or isolate other warehouse commands.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from src.warehouse.config import PURPOSE_FILES, ROOT, WarehouseSettings, load_settings
from src.warehouse.dbt_runner import (
    APPROVED_MODELS,
    SETUP_TIMEOUT_SECONDS,
    DbtError,
    _environment,
    _parse_settings,
)

GRAPH_JOB_TIMEOUT_SECONDS = 1200
PROTECTED_PROJECT_REF = "imvahwzlovgmaltuysmb"
APPROVED_LOCAL_MACROS = frozenset(
    f"macro.commercelens.{name}"
    for name in (
        "generate_schema_name",
        "commercelens_nullable_money",
        "commercelens_nullable_bigint",
        "commercelens_nullable_double",
        "commercelens_nullable_timestamp",
        "materialization_view_postgres",
    )
)
# Reviewed body, with CRLF/CR normalized to LF; never derived from mutable live files.
PRESERVING_VIEW_SHA256 = "90b4e858e91be8b22374ac0e3d186314ac9b5c5973ba92f388ec76dbf2cdad7b"
GraphCommand = Literal["build", "test"]
GraphContract = dict[str, str]


def _contained(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError
    return resolved


def _read_manifest(target: Path) -> dict[str, Any]:
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError
    invocation = metadata.get("invocation_id")
    if not isinstance(invocation, str) or not invocation:
        raise ValueError
    return manifest


def _graph_contract(manifest: dict[str, Any]) -> GraphContract:
    """Validate executable coverage and retain stable preflight/live node contracts."""
    if not isinstance(manifest, dict):
        raise ValueError
    if any(
        manifest.get(key)
        for key in ("disabled", "unit_tests", "functions", "saved_queries", "exposures")
    ):
        raise ValueError
    nodes = manifest["nodes"]
    approved = {f"model.commercelens.{name}" for name in APPROVED_MODELS}
    source_names = {
        name.removeprefix("stg_") for name in APPROVED_MODELS if name.startswith("stg_")
    }
    sources = manifest["sources"]
    if not isinstance(nodes, dict) or not isinstance(sources, dict) or set(nodes) & set(sources):
        raise ValueError
    if set(sources) != {f"source.commercelens.raw.{name}" for name in source_names}:
        raise ValueError
    models: set[str] = set()
    tests: set[str] = set()
    contract: GraphContract = {}
    for unique_id, node in {**nodes, **sources}.items():
        if not isinstance(unique_id, str) or not isinstance(node, dict):
            raise ValueError
        config = node["config"]
        if not isinstance(config, dict):
            raise ValueError
        if node["unique_id"] != unique_id or node["package_name"] != "commercelens":
            raise ValueError
        if config["enabled"] is not True or any(
            config.get(key) for key in ("pre-hook", "post-hook", "pre_hook", "post_hook")
        ):
            raise ValueError
        resource = node["resource_type"]
        if resource == "model":
            name = unique_id.removeprefix("model.commercelens.")
            schema = "staging" if name.startswith("stg_") else "core"
            if name in {"mart_order_components", "mart_order_kpis", "mart_item_kpis"}:
                schema = "marts"
            if unique_id not in approved or config["materialized"] != "view":
                raise ValueError
            if node["schema"] != schema or node["name"] != name or node["alias"] != name:
                raise ValueError
            models.add(unique_id)
        elif resource == "test":
            if not unique_id.startswith("test.commercelens."):
                raise ValueError
            if str(config["severity"]).lower() != "error" or config["store_failures"] is not False:
                raise ValueError
            if (
                config["error_if"] != "!= 0"
                or config["warn_if"] != "!= 0"
                or config["fail_calc"] != "count(*)"
                or config.get("store_failures_as") not in (None, "ephemeral")
                or any(config.get(key) is not None for key in ("where", "limit", "sql_header"))
            ):
                raise ValueError
            tests.add(unique_id)
        elif resource == "source":
            name = unique_id.removeprefix("source.commercelens.raw.")
            if (
                unique_id not in sources
                or node["name"] != name
                or node["identifier"] != name
                or node["schema"] != "raw"
                or node["source_name"] != "raw"
            ):
                raise ValueError
        else:
            raise ValueError
        if node["database"] != "postgres":
            raise ValueError
        relation_dependencies: list[str] = []
        if unique_id in nodes:
            depends_on = node["depends_on"]
            if not isinstance(depends_on, dict) or not isinstance(depends_on.get("nodes"), list):
                raise ValueError
            dependencies = depends_on["nodes"]
            if not all(isinstance(key, str) for key in dependencies):
                raise ValueError
            if not set(dependencies) <= approved | set(sources):
                raise ValueError
            relation_dependencies = sorted(dependencies)
        # Compilation adds runtime macro dependencies; relation references stay fixed.
        signature = {
            key: node.get(key)
            for key in (
                "resource_type",
                "name",
                "alias",
                "database",
                "schema",
                "config",
                "raw_code",
                "columns",
                "test_metadata",
                "checksum",
                "package_name",
                "unique_id",
                "source_name",
                "identifier",
            )
        }
        signature["depends_on"] = {"nodes": relation_dependencies}
        contract[unique_id] = json.dumps(signature, sort_keys=True)
    if models != approved or not tests:
        raise ValueError
    for unique_id in tests:
        dependencies = set(nodes[unique_id]["depends_on"]["nodes"])
        if not dependencies or not dependencies <= models | set(sources):
            raise ValueError
    if any(
        not any(model in nodes[test]["depends_on"]["nodes"] for test in tests) for model in models
    ):
        raise ValueError
    macros = manifest["macros"]
    if not isinstance(macros, dict) or any(
        not isinstance(key, str) or not isinstance(node, dict) for key, node in macros.items()
    ):
        raise ValueError
    local_macros = {
        key: node
        for key, node in macros.items()
        if key.startswith("macro.commercelens.") or node.get("package_name") == "commercelens"
    }
    if set(local_macros) != APPROVED_LOCAL_MACROS:
        raise ValueError
    for unique_id, macro in local_macros.items():
        if (
            macro["unique_id"] != unique_id
            or macro["resource_type"] != "macro"
            or macro["package_name"] != "commercelens"
            or macro["name"] != unique_id.removeprefix("macro.commercelens.")
        ):
            raise ValueError
        sql = macro["macro_sql"]
        if not isinstance(sql, str) or not sql:
            raise ValueError
        sql = sql.replace("\r\n", "\n").replace("\r", "\n")
        if unique_id == "macro.commercelens.materialization_view_postgres" and (
            hashlib.sha256(sql.encode("utf-8")).hexdigest() != PRESERVING_VIEW_SHA256
        ):
            raise ValueError
        signature = {
            key: macro.get(key)
            for key in (
                "unique_id",
                "name",
                "resource_type",
                "package_name",
                "arguments",
                "config",
                "supported_languages",
            )
        }
        signature["macro_sql"] = sql
        contract[unique_id] = json.dumps(signature, sort_keys=True)
    return contract


def _verify_graph_results(target: Path, command: GraphCommand, expected: GraphContract) -> None:
    try:
        if command not in ("build", "test"):
            raise ValueError
        manifest = _read_manifest(target)
        if _graph_contract(manifest) != expected:
            raise ValueError
        result = json.loads((target / "run_results.json").read_text(encoding="utf-8"))
        if result["metadata"]["invocation_id"] != manifest["metadata"]["invocation_id"]:
            raise ValueError
        results = result["results"]
        if not isinstance(results, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("unique_id"), str)
            for item in results
        ):
            raise ValueError
        actual = {item["unique_id"]: item["status"] for item in results}
        if any(item["failures"] != 0 for item in results if item["unique_id"].startswith("test.")):
            raise ValueError
        required = {key: "pass" for key in expected if key.startswith("test.")}
        if command == "build":
            required.update({key: "success" for key in expected if key.startswith("model.")})
        if len(actual) != len(results) or actual != required:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise DbtError(
            "dbt did not verify the complete graph results; artifacts retained"
        ) from None


def _run_phase(
    command: str,
    artifacts: Path,
    settings: WarehouseSettings,
    certificate: Path,
    timeout: int,
    *,
    select: str | None = None,
) -> Path:
    target = artifacts / "target"
    args = [
        sys.executable,
        "-I",
        "-m",
        "dbt.cli.main",
        command,
        "--project-dir",
        str(ROOT / "dbt"),
        "--profiles-dir",
        str(ROOT / "dbt" / "profiles"),
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
        "--target-path",
        str(target),
    ]
    if select is not None:
        args.extend(["--select", select, "--indirect-selection", "eager"])
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=_environment(settings, certificate),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DbtError(f"dbt graph {command} exceeded its {timeout}-second limit") from None
    except (OSError, ValueError):
        raise DbtError("dbt graph could not start; no subprocess detail logged") from None
    if result.returncode != 0:
        raise DbtError(f"dbt graph {command} failed; no subprocess detail logged")
    return target


def run_dbt_graph(
    command: GraphCommand, *, settings_root: Path, expected_project_ref: str
) -> dict[str, str | bool | int]:
    """Preflight the fixed graph, then build/test only the isolated test target."""
    if command not in ("build", "test"):
        raise DbtError("Choose build or test for the fixed dbt graph")
    try:
        if (
            not isinstance(settings_root, Path)
            or not isinstance(expected_project_ref, str)
            or not re.fullmatch(r"[a-z]{20}", expected_project_ref)
            or expected_project_ref == PROTECTED_PROJECT_REF
            or any(name.upper().startswith("WAREHOUSE_") for name in os.environ)
        ):
            raise ValueError
        isolated = settings_root.resolve(strict=True)
        repo = ROOT.resolve()
        if not isolated.is_dir() or isolated.is_relative_to(repo) or repo.is_relative_to(isolated):
            raise ValueError
        config = _contained(isolated, isolated / PURPOSE_FILES["transformer"])
        if not config.is_file():
            raise ValueError
        settings = load_settings(isolated, purpose="transformer")
        if (
            settings.purpose != "transformer"
            or settings.environment != "test"
            or settings.project_ref != expected_project_ref
            or settings.project_ref == PROTECTED_PROJECT_REF
        ):
            raise ValueError
        certificate = _contained(isolated, settings.certificate_path(isolated))
        if not certificate.is_file():
            raise ValueError
        project = ROOT / "dbt"
        if (
            not (project / "dbt_project.yml").is_file()
            or not (project / "profiles" / "profiles.yml").is_file()
        ):
            raise ValueError
        artifacts = _contained(
            isolated, isolated / ".artifacts" / "dbt-reconstruction" / uuid4().hex
        )
        artifacts.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, TypeError):
        raise DbtError(
            "Invalid isolated dbt target, settings, certificate or artifact paths"
        ) from None
    synthetic = _parse_settings()
    preflight = _run_phase(
        "parse", artifacts / "preflight", synthetic, synthetic.sslrootcert, SETUP_TIMEOUT_SECONDS
    )
    try:
        expected = _graph_contract(_read_manifest(preflight))
    except (OSError, ValueError, KeyError, TypeError):
        raise DbtError("dbt preflight did not verify the fixed graph; artifacts retained") from None
    target = _run_phase(
        command, artifacts / "live", settings, certificate, GRAPH_JOB_TIMEOUT_SECONDS
    )
    _verify_graph_results(target, command, expected)
    return {
        "command": f"dbt-{command}-graph",
        "status": "passed",
        "offline": False,
        "project_ref": expected_project_ref,
        "artifacts": str(artifacts),
        "models": len(APPROVED_MODELS),
        "tests": sum(key.startswith("test.") for key in expected),
    }
