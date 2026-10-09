"""Offline failure proofs for the bounded Phase 5 selected-mart runner."""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_warehouse_dbt_reconstruction import (
    PROJECT_REF,
    PROTECTED_REF,
    SECRET,
    _manifest,
    _write_artifacts,
    _write_settings,
)
from test_warehouse_dbt_reconstruction import repo_root as repo_root

from src.warehouse import dbt_reconstruction as graph
from src.warehouse import dbt_selected as selected
from src.warehouse import reconstruction as isolated


@pytest.fixture
def harness(repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in tuple(os.environ):
        if name.upper().startswith(("WAREHOUSE_", "PG")):
            monkeypatch.delenv(name)
    root = tmp_path / "isolated"
    root.mkdir()
    (root / "ca.crt").write_text("synthetic CA", encoding="utf-8")
    _write_settings(root)
    monkeypatch.setattr(selected, "ROOT", repo_root)
    monkeypatch.setattr(isolated, "ROOT", repo_root)
    state = SimpleNamespace(
        root=root,
        repo=repo_root,
        calls=[],
        protected=[],
        mutate_preflight=lambda manifest: None,
        mutate_live=lambda manifest: None,
        mutate_results=lambda result: None,
        live_failure=None,
    )
    monkeypatch.setattr(isolated, "protect_credential_file", state.protected.append)

    def execute(args, **kwargs):
        state.calls.append({"args": args, **kwargs})
        command = args[4]
        manifest = _manifest("synthetic-" + command)
        # Eager selection must include a multi-parent test, even if its other
        # parent is not selected. It must not build that other parent.
        cross_test = manifest["nodes"]["test.commercelens.fact_orders_contract"]
        cross_test["depends_on"]["nodes"].extend(
            ["model.commercelens.mart_order_kpis", "model.commercelens.mart_item_kpis"]
        )
        result = None
        if command == "parse":
            state.mutate_preflight(manifest)
        else:
            if state.live_failure is not None:
                raise state.live_failure
            state.mutate_live(manifest)
            model_id = "model.commercelens." + args[args.index("--select") + 1]
            result = {
                "metadata": copy.deepcopy(manifest["metadata"]),
                "results": [
                    {"unique_id": unique_id, "status": "pass", "failures": 0}
                    for unique_id, node in manifest["nodes"].items()
                    if node["resource_type"] == "test" and model_id in node["depends_on"]["nodes"]
                ],
            }
            if command == "build":
                result["results"].append(
                    {"unique_id": model_id, "status": "success", "failures": None}
                )
            state.mutate_results(result)
        target = Path(args[args.index("--target-path") + 1])
        _write_artifacts(target, manifest, result)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(graph.subprocess, "run", execute)
    return state


def run(harness, command="build", select="mart_order_kpis", **kwargs):
    return selected.run_dbt_selected(
        command,
        select=select,
        settings_root=kwargs.get("settings_root", harness.root),
        expected_project_ref=kwargs.get("expected_project_ref", PROJECT_REF),
    )


@pytest.mark.parametrize("command", ["build", "test"])
@pytest.mark.parametrize("model", ["mart_order_kpis", "mart_item_kpis"])
def test_exact_selection_and_all_eager_tests_retain_prior_outputs(harness, command, model):
    receipt = run(harness, command, model)
    assert receipt["status"] == "passed"
    assert receipt["tests"] == 2
    assert receipt["models"] == int(command == "build")
    assert receipt["build_committed"] is (command == "build")
    assert len(receipt["graph_contract_sha256"]) == 64
    assert harness.protected == [harness.root / ".env.warehouse.transformer"]
    assert [call["args"][4] for call in harness.calls] == ["parse", command]
    for call in harness.calls:
        args = call["args"]
        assert call["cwd"] == harness.repo
        assert call["stdin"] == call["stdout"] == call["stderr"] == subprocess.DEVNULL
        assert call["timeout"] == (120 if args[4] == "parse" else 180)
        assert SECRET not in repr(args)
        assert "--full-refresh" not in args and "--exclude" not in args
        if args[4] == "parse":
            assert "--select" not in args
            assert call["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] != SECRET
        else:
            assert args[args.index("--select") + 1] == model
            assert args[args.index("--indirect-selection") + 1] == "eager"
            assert call["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] == SECRET
    first = Path(receipt["artifacts"])
    first_bytes = (first / "receipt.json").read_bytes()
    second = Path(run(harness, command, model)["artifacts"])
    assert first != second and first.is_relative_to(harness.root)
    assert (first / "receipt.json").read_bytes() == first_bytes


@pytest.mark.parametrize(
    ("command", "model"),
    [
        ("parse", "mart_order_kpis"),
        ("clean", "mart_order_kpis"),
        ("build", "+mart_order_kpis"),
        ("build", "mart_order_kpis+"),
        ("build", "mart_order_kpis mart_item_kpis"),
        ("build", "mart_order_components"),
        ("build", "*"),
    ],
)
def test_selection_and_command_fail_before_settings(harness, command, model):
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness, command, model)
    assert not harness.calls and not harness.protected
    assert error.value.evidence["live_attempted"] is False
    assert error.value.evidence["build_committed"] is False


@pytest.mark.parametrize("reference", [PROTECTED_REF, "", "A" * 20])
def test_original_or_invalid_target_rejected_before_private_settings(harness, reference):
    with pytest.raises(selected.SelectedDbtError):
        run(harness, expected_project_ref=reference)
    assert not harness.calls and not harness.protected


@pytest.mark.parametrize("location", ["repo", "within", "ancestor", "missing"])
def test_default_or_nonisolated_settings_rejected(harness, location):
    paths = {
        "repo": harness.repo,
        "within": harness.repo / "dbt",
        "ancestor": harness.repo.parent,
        "missing": harness.root / "missing",
    }
    with pytest.raises(selected.SelectedDbtError):
        run(harness, settings_root=paths[location])
    assert not harness.calls and not harness.protected


@pytest.mark.parametrize("variable", ["WAREHOUSE_PASSWORD", "PGPASSWORD", "PGSERVICEFILE"])
def test_ambient_routing_rejected(harness, monkeypatch, variable):
    monkeypatch.setenv(variable, SECRET)
    with pytest.raises(selected.SelectedDbtError):
        run(harness)
    assert not harness.calls and not harness.protected


@pytest.mark.parametrize(
    "changed",
    [
        {"ENVIRONMENT": "development"},
        {"PROJECT_REF": "z" * 20, "HOST": "db." + "z" * 20 + ".supabase.co"},
        {"SSLROOTCERT": "missing.crt"},
        {"SSLROOTCERT": "../escape.crt"},
    ],
)
def test_mismatched_settings_or_certificate_rejected(harness, changed):
    _write_settings(harness.root, **changed)
    with pytest.raises(selected.SelectedDbtError):
        run(harness)
    assert not harness.calls


def test_hardlinked_private_file_rejected_before_protection(harness):
    os.link(harness.root / ".env.warehouse.transformer", harness.root / "retained-link")
    with pytest.raises(selected.SelectedDbtError):
        run(harness)
    assert not harness.calls and not harness.protected


@pytest.mark.parametrize("change", ["missing_model", "unsafe_test", "unsafe_macro"])
def test_whole_graph_preflight_rejects_unrelated_unsafe_nodes(harness, change):
    def mutate(manifest):
        if change == "missing_model":
            manifest["nodes"].pop("model.commercelens.stg_customers")
        elif change == "unsafe_test":
            manifest["nodes"]["test.commercelens.stg_customers_contract"]["config"][
                "store_failures"
            ] = True
        else:
            manifest["macros"]["macro.commercelens.materialization_view_postgres"]["macro_sql"] += (
                "\n-- unreviewed materialization"
            )

    harness.mutate_preflight = mutate
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness)
    assert len(harness.calls) == 1
    assert error.value.evidence["stage"] == "preflight"
    assert error.value.evidence["build_committed"] is False
    failure = Path(error.value.evidence["artifacts"]) / "failure.json"
    assert json.loads(failure.read_text())["live_attempted"] is False


@pytest.mark.parametrize("change", ["unrelated_sql", "macro", "preflight_invocation"])
def test_live_manifest_must_match_entire_preflight_and_new_invocation(harness, change):
    def mutate(manifest):
        if change == "unrelated_sql":
            manifest["nodes"]["model.commercelens.stg_customers"]["raw_code"] += " -- changed"
        elif change == "macro":
            manifest["macros"]["macro.commercelens.generate_schema_name"]["macro_sql"] += " "
        else:
            manifest["metadata"]["invocation_id"] = "synthetic-parse"

    harness.mutate_live = mutate
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness)
    assert error.value.evidence["stage"] == "results"
    assert error.value.evidence["build_committed"] is None


@pytest.mark.parametrize(
    "change", ["missing", "extra_model", "duplicate", "skipped", "failures", "invocation"]
)
def test_partial_excess_or_mismatched_results_never_claim_success(harness, change):
    def mutate(result):
        rows = result["results"]
        if change == "missing":
            rows.pop(0)
        elif change == "extra_model":
            rows.append({"unique_id": "model.commercelens.fact_orders", "status": "success"})
        elif change == "duplicate":
            rows.append(rows[0])
        elif change == "skipped":
            rows[0]["status"] = "skipped"
        elif change == "failures":
            rows[0]["failures"] = 1
        else:
            result["metadata"]["invocation_id"] = "stale-other-run"

    harness.mutate_results = mutate
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness)
    assert error.value.evidence["live_attempted"] is True
    assert error.value.evidence["build_committed"] is None
    artifacts = Path(error.value.evidence["artifacts"])
    assert not (artifacts / "receipt.json").exists()
    assert (artifacts / "live/target/run_results.json").is_file()


@pytest.mark.parametrize(
    "failure", [OSError(SECRET), subprocess.TimeoutExpired(SECRET, 180), KeyboardInterrupt()]
)
def test_live_interruption_retains_ambiguous_commit_and_safe_diagnostics(harness, failure, capsys):
    harness.live_failure = failure
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness)
    evidence = error.value.evidence
    assert evidence["live_attempted"] is True and evidence["build_committed"] is None
    assert "Inspect selected view" in evidence["recovery"]
    assert SECRET not in str(error.value) + json.dumps(evidence)
    assert capsys.readouterr() == ("", "")


def test_receipt_failure_preserves_verified_commit_evidence(harness, monkeypatch):
    write = selected._write_evidence

    def fail_success(path, evidence):
        if path.name == "receipt.json":
            raise OSError(SECRET)
        write(path, evidence)

    monkeypatch.setattr(selected, "_write_evidence", fail_success)
    with pytest.raises(selected.SelectedDbtError) as error:
        run(harness)
    assert error.value.evidence["stage"] == "receipt"
    assert error.value.evidence["build_committed"] is True


@pytest.mark.parametrize("failure", ["preflight", "live", "after", None])
def test_native_build_dispatch_and_commit_failure_evidence(tmp_path, monkeypatch, capsys, failure):
    from scripts import phase5_native as native

    monkeypatch.setattr(native, "ROOT", tmp_path)
    monkeypatch.setattr(native, "_isolated_root", lambda *args: tmp_path)
    monkeypatch.setattr(native, "_settings", lambda *args: object())
    calls = []

    def metadata(settings):
        calls.append("metadata")
        if failure == "after" and len(calls) > 1:
            raise ValueError(SECRET)
        return {"relations": [], "raw_bytes": 1}

    def build(command, *, select, settings_root, expected_project_ref):
        assert command == "build" and select == "mart_item_kpis"
        assert settings_root == tmp_path and expected_project_ref == PROJECT_REF
        if failure in ("preflight", "live"):
            raise selected.SelectedDbtError(
                {
                    "stage": failure,
                    "live_attempted": failure == "live",
                    "build_committed": None if failure == "live" else False,
                }
            )
        return {"status": "passed", "live_attempted": True, "build_committed": True}

    monkeypatch.setattr(native, "metadata", metadata)
    monkeypatch.setattr(native, "run_dbt_selected", build)
    monkeypatch.setattr(
        "sys.argv",
        [
            "native",
            "build-item",
            "--settings-root",
            str(tmp_path),
            "--expected-project-ref",
            PROJECT_REF,
        ],
    )
    assert native.main() == (1 if failure else 0)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    if failure:
        receipt = json.loads(
            next((tmp_path / ".artifacts/phase-5").glob("*/failure.json")).read_text()
        )
        assert receipt["build_attempted"] is (failure != "preflight")
        assert receipt["build_committed"] is (
            True if failure == "after" else None if failure == "live" else False
        )
        assert receipt["grant_attempted"] is False
