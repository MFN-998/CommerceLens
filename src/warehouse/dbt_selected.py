"""Build/test one Phase 5 mart on an explicit isolated target, retaining all evidence.

Every execution preflights the complete closed graph offline. Selection never
includes ancestors; failures after dispatch may leave a committed selected view.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.warehouse.config import ROOT
from src.warehouse.dbt_reconstruction import (
    GraphCommand,
    GraphContract,
    _contained,
    _graph_contract,
    _read_manifest,
    _run_phase,
)
from src.warehouse.dbt_runner import (
    MODEL_JOB_TIMEOUT_SECONDS,
    SETUP_TIMEOUT_SECONDS,
    DbtError,
    _parse_settings,
)
from src.warehouse.reconstruction import _isolated_root, _settings

SELECTED_MARTS = frozenset({"mart_order_kpis", "mart_item_kpis"})
FAILURE_MESSAGE = (
    "Selected dbt step failed; inspect retained evidence before retrying; no detail logged"
)


class SelectedDbtError(DbtError):
    """Carry fixed recovery facts when success cannot be proved."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__(FAILURE_MESSAGE)
        self.evidence = evidence


def _write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(evidence, sort_keys=True, indent=2) + "\n")


def _selected_tests(manifest: dict[str, Any], select: str) -> set[str]:
    """Match dbt eager indirect selection, including multi-parent tests."""
    model_id = f"model.commercelens.{select}"
    tests = {
        unique_id
        for unique_id, node in manifest["nodes"].items()
        if node["resource_type"] == "test" and model_id in node["depends_on"]["nodes"]
    }
    if not tests:
        raise ValueError
    return tests


def _verify_selected_results(
    target: Path,
    command: GraphCommand,
    select: str,
    expected: GraphContract,
    tests: set[str],
    preflight_invocation: str,
) -> None:
    manifest = _read_manifest(target)
    if _graph_contract(manifest) != expected:
        raise ValueError
    invocation = manifest["metadata"]["invocation_id"]
    if invocation == preflight_invocation:
        raise ValueError
    result = json.loads((target / "run_results.json").read_text(encoding="utf-8"))
    if result["metadata"]["invocation_id"] != invocation:
        raise ValueError
    results = result["results"]
    if not isinstance(results, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("unique_id"), str) for item in results
    ):
        raise ValueError
    actual = {item["unique_id"]: item["status"] for item in results}
    required = dict.fromkeys(tests, "pass")
    if command == "build":
        required[f"model.commercelens.{select}"] = "success"
    if len(actual) != len(results) or actual != required:
        raise ValueError
    if any(item["failures"] != 0 for item in results if item["unique_id"] in tests):
        raise ValueError


def run_dbt_selected(
    command: GraphCommand,
    *,
    select: str,
    settings_root: Path,
    expected_project_ref: str,
) -> dict[str, Any]:
    """Run one reviewed mart and all its tests, never another model or a retry."""
    artifacts: Path | None = None
    evidence: dict[str, Any] = {
        "status": "failed",
        "stage": "target",
        "live_attempted": False,
        "build_committed": False,
        "private_detail_logged": False,
        "recovery": "No live dbt command attempted",
    }
    try:
        if command not in ("build", "test") or select not in SELECTED_MARTS:
            raise ValueError
        isolated = _isolated_root(settings_root, expected_project_ref)
        settings = _settings(isolated, "transformer", expected_project_ref)
        project = ROOT / "dbt"
        if (
            not (project / "dbt_project.yml").is_file()
            or not (project / "profiles" / "profiles.yml").is_file()
        ):
            raise ValueError
        artifacts = _contained(isolated, isolated / ".artifacts" / "dbt-selected" / uuid4().hex)
        artifacts.mkdir(parents=True, exist_ok=False)
        evidence["artifacts"] = str(artifacts)
        evidence["stage"] = "preflight"
        synthetic = _parse_settings()
        preflight = _run_phase(
            "parse",
            artifacts / "preflight",
            synthetic,
            synthetic.sslrootcert,
            SETUP_TIMEOUT_SECONDS,
        )
        manifest = _read_manifest(preflight)
        expected = _graph_contract(manifest)
        tests = _selected_tests(manifest, select)
        evidence.update(
            stage="live",
            live_attempted=True,
            build_committed=None if command == "build" else False,
            recovery="Inspect selected view and test evidence before retry",
        )
        target = _run_phase(
            command,
            artifacts / "live",
            settings,
            settings.sslrootcert,
            MODEL_JOB_TIMEOUT_SECONDS,
            select=select,
        )
        evidence["stage"] = "results"
        _verify_selected_results(
            target, command, select, expected, tests, manifest["metadata"]["invocation_id"]
        )
        evidence.update(stage="receipt", build_committed=command == "build")
        receipt = {
            "command": f"dbt-{command}-selected",
            "selection": select,
            "status": "passed",
            "offline": False,
            "project_ref": expected_project_ref,
            "artifacts": str(artifacts),
            "models": int(command == "build"),
            "tests": len(tests),
            "graph_contract_sha256": hashlib.sha256(
                json.dumps(expected, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "live_attempted": True,
            "build_committed": command == "build",
        }
        _write_evidence(artifacts / "receipt.json", receipt)
        return receipt
    except (Exception, KeyboardInterrupt):
        if artifacts is not None:
            try:
                _write_evidence(artifacts / "failure.json", evidence)
            except OSError:
                # The safe exception still carries recovery facts if disk writes fail.
                pass
        raise SelectedDbtError(evidence) from None
