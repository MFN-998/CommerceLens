"""Offline proof of isolated full-graph reconstruction guards and dbt evidence.

Subprocess fixtures never connect. The one real parse uses synthetic settings
with network/adapter guards, the unmodified accepted graph and retained output.
Neither accepted credentials nor warehouse records are read by this suite.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.warehouse import dbt_reconstruction as reconstruction
from src.warehouse.dbt_runner import DbtError

ACCEPTED_ROOT = reconstruction.ROOT
PROJECT = ACCEPTED_ROOT / "dbt"
PROJECT_REF = "abcdefghijklmnopqrst"
PROTECTED_REF = "imvahwzlovgmaltuysmb"
SECRET = "synthetic-reconstruction-password-do-not-print"
MODEL_SCHEMAS = {
    **{
        name: "staging"
        for name in (
            "stg_customers",
            "stg_sellers",
            "stg_category_translation",
            "stg_products",
            "stg_orders",
            "stg_order_items",
            "stg_order_payments",
            "stg_order_reviews",
            "stg_geolocation",
        )
    },
    **{
        name: "core"
        for name in (
            "dim_location",
            "dim_seller",
            "dim_customer",
            "dim_product",
            "dim_date",
            "int_order_customers",
            "fact_orders",
            "fact_order_items",
            "fact_payments",
            "fact_reviews",
        )
    },
    "mart_order_components": "marts",
    "mart_order_kpis": "marts",
}


@pytest.fixture(autouse=True)
def no_ambient_warehouse_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Delete variables only from the test process environment, never source files.
    for name in tuple(reconstruction.os.environ):
        if name.upper().startswith("WAREHOUSE_"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(PROJECT, root / "dbt", ignore=shutil.ignore_patterns("target", "logs"))
    monkeypatch.setattr(reconstruction, "ROOT", root)
    return root


@pytest.fixture
def settings_root(tmp_path: Path) -> Path:
    root = tmp_path / "isolated-settings"
    root.mkdir()
    (root / "ca.crt").write_text("synthetic public CA placeholder", encoding="utf-8")
    _write_settings(root)
    return root


def _write_settings(root: Path, **overrides: str) -> None:
    fields = {
        "PURPOSE": "transformer",
        "ENVIRONMENT": "test",
        "PROJECT_REF": PROJECT_REF,
        "HOST": f"db.{PROJECT_REF}.supabase.co",
        "USER": "commercelens_transform",
        "PASSWORD": SECRET,
        "SSLROOTCERT": "ca.crt",
    }
    fields.update(overrides)
    (root / ".env.warehouse.transformer").write_text(
        "".join(f"WAREHOUSE_{name}={value}\n" for name, value in fields.items()), encoding="utf-8"
    )


def _manifest(invocation: str = "synthetic-preflight") -> dict:
    nodes = {}
    for name, schema in MODEL_SCHEMAS.items():
        model_id = f"model.commercelens.{name}"
        test_id = f"test.commercelens.{name}_contract"
        nodes[model_id] = {
            "unique_id": model_id,
            "name": name,
            "alias": name,
            "resource_type": "model",
            "package_name": "commercelens",
            "database": "postgres",
            "schema": schema,
            "config": {
                "enabled": True,
                "materialized": "view",
                "schema": schema,
                "pre-hook": [],
                "post-hook": [],
            },
            "depends_on": {"nodes": []},
            "raw_code": "select 1 as synthetic_column",
            "checksum": {"name": "sha256", "checksum": "synthetic-model-checksum"},
        }
        nodes[test_id] = {
            "unique_id": test_id,
            "name": name + "_contract",
            "alias": name + "_contract",
            "resource_type": "test",
            "package_name": "commercelens",
            "database": "postgres",
            "schema": "staging",
            "config": {
                "enabled": True,
                "materialized": "test",
                "severity": "error",
                "store_failures": False,
                "store_failures_as": None,
                "fail_calc": "count(*)",
                "error_if": "!= 0",
                "warn_if": "!= 0",
                "limit": None,
                "where": None,
                "pre-hook": [],
                "post-hook": [],
            },
            "depends_on": {"nodes": [model_id]},
            "raw_code": "select 1 where false",
            "checksum": {"name": "sha256", "checksum": "synthetic-test-checksum"},
        }
    sources = {}
    for model_name in MODEL_SCHEMAS:
        if not model_name.startswith("stg_"):
            continue
        name = model_name.removeprefix("stg_")
        identifier = f"source.commercelens.raw.{name}"
        sources[identifier] = {
            "unique_id": identifier,
            "name": name,
            "identifier": name,
            "source_name": "raw",
            "resource_type": "source",
            "package_name": "commercelens",
            "database": "postgres",
            "schema": "raw",
            "config": {"enabled": True},
        }
    return {
        "metadata": {"invocation_id": invocation},
        "nodes": nodes,
        "sources": sources,
        "disabled": {},
        "unit_tests": {},
        "macros": _local_macros(),
    }


def _local_macros() -> dict:
    # dbt stores each Jinja definition, excluding surrounding file comments.
    # Read the accepted definitions directly so no ignored artifact is required.
    macros = {}
    definitions = re.compile(
        r"{%-?\s*(macro|materialization)\s+([A-Za-z_][A-Za-z_0-9]*)\b"
        r".*?{%-?\s*end(?:macro|materialization)\s*-?%}",
        re.DOTALL,
    )
    for path in (PROJECT / "macros").rglob("*.sql"):
        with path.open(encoding="utf-8", newline="") as stream:
            content = stream.read()
        for match in definitions.finditer(content):
            name = match[2] if match[1] == "macro" else "materialization_view_postgres"
            unique_id = "macro.commercelens." + name
            assert unique_id not in macros
            macros[unique_id] = {
                "unique_id": unique_id,
                "name": name,
                "resource_type": "macro",
                "package_name": "commercelens",
                "macro_sql": match[0],
                "depends_on": {"macros": []},
            }
    assert len(macros) == 6
    return macros


def _results(manifest: dict, command: str) -> dict:
    return {
        "metadata": copy.deepcopy(manifest["metadata"]),
        "results": [
            {
                "unique_id": identifier,
                "status": "success" if node["resource_type"] == "model" else "pass",
                "failures": None if node["resource_type"] == "model" else 0,
            }
            for identifier, node in manifest["nodes"].items()
            if command == "build" or node["resource_type"] == "test"
        ],
    }


def _write_artifacts(target: Path, manifest: dict, results: dict | None = None) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if results is not None:
        (target / "run_results.json").write_text(json.dumps(results), encoding="utf-8")


@pytest.fixture
def captured_runs(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    def capture(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append({"args": args, **kwargs})
        command = args[4]
        target = Path(args[args.index("--target-path") + 1])
        manifest = _manifest("synthetic-" + command)
        _write_artifacts(
            target, manifest, None if command == "parse" else _results(manifest, command)
        )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reconstruction.subprocess, "run", capture)
    return calls


def _run(settings: Path, command: str = "build", expected_ref: str = PROJECT_REF) -> dict:
    return reconstruction.run_dbt_graph(
        command, settings_root=settings, expected_project_ref=expected_ref
    )


@pytest.mark.parametrize("command", ["build", "test"])
def test_fixed_full_graph_uses_isolated_settings_redacted_environment_and_retained_outputs(
    repo_root: Path,
    settings_root: Path,
    captured_runs: list[dict],
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    for name in ("DBT_ENV_SECRET_UNRELATED", "DBT_PROFILES_DIR", "PGPASSWORD", "PGSERVICEFILE"):
        monkeypatch.setenv(name, "ambient-secret-that-must-be-removed")
    first = _run(settings_root, command)
    assert first["status"] == "passed"
    assert first["offline"] is False
    assert [call["args"][4] for call in captured_runs] == ["parse", command]
    for call in captured_runs:
        args, environment = call["args"], call["env"]
        assert args[args.index("--project-dir") + 1] == str(repo_root / "dbt")
        assert args[args.index("--profiles-dir") + 1] == str(repo_root / "dbt/profiles")
        assert call["cwd"] == repo_root
        assert call["stdin"] == call["stdout"] == call["stderr"] == subprocess.DEVNULL
        assert call["timeout"] == (120 if args[4] == "parse" else 1200)
        assert "--no-partial-parse" in args and "--no-use-v2-parser" in args
        assert "--select" not in args and "--exclude" not in args
        assert "--store-failures" not in args and "--full-refresh" not in args
        assert environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] == "false"
        assert environment["PGOPTIONS"] == (
            "-c statement_timeout=60000 -c lock_timeout=10000 "
            "-c idle_in_transaction_session_timeout=60000"
        )
        assert "ambient-secret-that-must-be-removed" not in environment.values()
        assert SECRET not in repr(args)
    assert captured_runs[0]["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] != SECRET
    assert captured_runs[1]["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] == SECRET
    assert captured_runs[1]["env"]["DBT_ENV_SECRET_WAREHOUSE_SSLROOTCERT"] == str(
        settings_root / "ca.crt"
    )
    original_targets = [
        Path(call["args"][call["args"].index("--target-path") + 1]) for call in captured_runs
    ]
    keep = original_targets[0] / "keep.txt"
    keep.write_text("earlier proof retained", encoding="utf-8")
    _run(settings_root, command)
    assert (
        len({call["args"][call["args"].index("--target-path") + 1] for call in captured_runs}) == 4
    )
    assert keep.read_text("utf-8") == "earlier proof retained"
    assert all(
        path.is_file() for target in original_targets for path in (target / "manifest.json",)
    )
    profile = pytest.importorskip("yaml").safe_load(
        (repo_root / "dbt/profiles/profiles.yml").read_text("utf-8")
    )["commercelens"]["outputs"]["development"]
    assert (profile["role"], profile["sslmode"], profile["threads"], profile["retries"]) == (
        "commercelens_transformer",
        "verify-full",
        1,
        0,
    )


@pytest.mark.parametrize("command", ["parse", "debug", "run", "clean", "seed"])
def test_unapproved_commands_fail_before_settings_or_subprocess(
    settings_root: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr(
        reconstruction, "load_settings", lambda *a, **kw: pytest.fail("Settings read")
    )
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError):
        _run(settings_root, command)


@pytest.mark.parametrize("expected_ref", [PROTECTED_REF, "", "short", "A" * 20, "a" * 21])
def test_target_identity_guard_runs_before_private_settings_or_subprocess(
    settings_root: Path, monkeypatch: pytest.MonkeyPatch, expected_ref: str
) -> None:
    monkeypatch.setattr(
        reconstruction, "load_settings", lambda *a, **kw: pytest.fail("Settings read")
    )
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError):
        _run(settings_root, expected_ref=expected_ref)


@pytest.mark.parametrize("location", ["repo", "inside-repo", "parent-repo", "missing", "file"])
def test_settings_directory_must_exist_outside_the_fixed_repository(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    locations = {
        "repo": repo_root,
        "inside-repo": repo_root / "dbt",
        "parent-repo": repo_root.parent,
        "missing": settings_root / "missing-directory",
        "file": settings_root / "ca.crt",
    }
    monkeypatch.setattr(
        reconstruction, "load_settings", lambda *a, **kw: pytest.fail("Settings read")
    )
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError):
        _run(locations[location])


@pytest.mark.parametrize("name", ["WAREHOUSE_PASSWORD", "warehouse_host", "Warehouse_PURPOSE"])
def test_ambient_warehouse_overrides_are_refused_before_loading_configuration(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, SECRET)
    monkeypatch.setattr(
        reconstruction, "load_settings", lambda *a, **kw: pytest.fail("Settings read")
    )
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError) as error:
        _run(settings_root)
    assert SECRET not in str(error.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"PURPOSE": "admin", "USER": "postgres"},
        {"ENVIRONMENT": "development"},
        {"PROJECT_REF": PROTECTED_REF, "HOST": f"db.{PROTECTED_REF}.supabase.co"},
        {"PROJECT_REF": "zyxwvutsrqponmlkjihg", "HOST": "db.zyxwvutsrqponmlkjihg.supabase.co"},
        {"HOST": "localhost"},
        {"SSLROOTCERT": "missing.crt"},
        {"SSLROOTCERT": "../outside.crt"},
    ],
)
def test_wrong_purpose_environment_target_or_certificate_cannot_launch_dbt(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict
) -> None:
    (settings_root.parent / "outside.crt").write_text("synthetic CA", encoding="utf-8")
    _write_settings(settings_root, **overrides)
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError) as error:
        _run(settings_root)
    assert SECRET not in str(error.value)


def test_missing_purpose_specific_file_never_reads_other_credentials_or_launches_dbt(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "missing-transformer"
    settings.mkdir()
    (settings / ".env.warehouse").write_text(SECRET, encoding="utf-8")
    monkeypatch.setattr(
        reconstruction, "load_settings", lambda *a, **kw: pytest.fail("Settings read")
    )
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError):
        _run(settings)


def test_artifact_resolution_escape_is_refused_before_subprocess(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_resolve = Path.resolve

    def escaped_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        resolved = original_resolve(path, *args, **kwargs)
        if path.is_relative_to(settings_root / ".artifacts"):
            # Model a junction/symlink escape without creating one or touching
            # an external directory. The actual containment check must reject it.
            return settings_root.parent / "outside-artifacts"
        return resolved

    monkeypatch.setattr(Path, "resolve", escaped_resolve)
    monkeypatch.setattr(
        reconstruction.subprocess, "run", lambda *a, **kw: pytest.fail("dbt launched")
    )
    with pytest.raises(DbtError):
        _run(settings_root)
    assert not (settings_root / ".artifacts").exists()


def _mutate_graph(manifest: dict, mutation: str) -> None:
    model_id = "model.commercelens.stg_customers"
    test_id = "test.commercelens.stg_customers_contract"
    model, test = manifest["nodes"][model_id], manifest["nodes"][test_id]
    if mutation == "missing-model":
        del manifest["nodes"][model_id]
    elif mutation == "extra-model":
        node = copy.deepcopy(model)
        node.update(
            unique_id="model.commercelens.unapproved", name="unapproved", alias="unapproved"
        )
        manifest["nodes"][node["unique_id"]] = node
    elif mutation == "duplicate-model-identity":
        manifest["nodes"]["model.commercelens.duplicate"] = copy.deepcopy(model)
    elif mutation == "malformed-node":
        manifest["nodes"][model_id] = None
    elif mutation == "unknown-model-dependency":
        model["depends_on"]["nodes"] = ["model.commercelens.unapproved"]
    elif mutation == "disabled-model":
        model["config"]["enabled"] = False
    elif mutation == "wrong-schema":
        model["schema"] = "public"
    elif mutation == "table-materialization":
        model["config"]["materialized"] = "table"
    elif mutation == "wrong-alias":
        model["alias"] = "unexpected"
    elif mutation == "missing-test":
        del manifest["nodes"][test_id]
    elif mutation == "disabled-test":
        test["config"]["enabled"] = False
    elif mutation == "warning-test":
        test["config"]["severity"] = "warn"
    elif mutation == "failure-storage":
        test["config"]["store_failures"] = True
    elif mutation == "weak-test-threshold":
        test["config"]["error_if"] = "> 100"
    elif mutation == "limited-test":
        test["config"]["limit"] = 1
    elif mutation == "filtered-test":
        test["config"]["where"] = "false"
    elif mutation == "missing-source":
        del manifest["sources"]["source.commercelens.raw.customers"]
    elif mutation == "wrong-source-schema":
        manifest["sources"]["source.commercelens.raw.customers"]["schema"] = "public"
    elif mutation == "source-shadow":
        source_id = "source.commercelens.raw.customers"
        manifest["nodes"][source_id] = copy.deepcopy(manifest["sources"][source_id])
    elif mutation == "missing-view-macro":
        del manifest["macros"]["macro.commercelens.materialization_view_postgres"]
    elif mutation == "mutated-view-macro":
        manifest["macros"]["macro.commercelens.materialization_view_postgres"]["macro_sql"] += (
            " changed"
        )
    elif mutation == "missing-local-macro":
        del manifest["macros"]["macro.commercelens.commercelens_nullable_money"]
    elif mutation == "model-hook":
        model["config"]["pre-hook"] = ["select 1"]
    elif mutation == "test-hook":
        test["config"]["post-hook"] = ["select 1"]
    elif mutation == "unexpected-seed":
        node = copy.deepcopy(model)
        node.update(unique_id="seed.commercelens.unapproved", resource_type="seed")
        manifest["nodes"][node["unique_id"]] = node
    elif mutation == "unit-test":
        manifest["unit_tests"] = {"unit_test.commercelens.extra": {"config": {"enabled": True}}}
    elif mutation == "missing-invocation":
        manifest["metadata"]["invocation_id"] = ""
    else:
        raise AssertionError("Unknown graph mutation")


GRAPH_MUTATIONS = (
    "missing-model",
    "extra-model",
    "duplicate-model-identity",
    "malformed-node",
    "unknown-model-dependency",
    "disabled-model",
    "wrong-schema",
    "table-materialization",
    "wrong-alias",
    "missing-test",
    "disabled-test",
    "warning-test",
    "failure-storage",
    "weak-test-threshold",
    "limited-test",
    "filtered-test",
    "missing-source",
    "wrong-source-schema",
    "source-shadow",
    "missing-view-macro",
    "mutated-view-macro",
    "missing-local-macro",
    "model-hook",
    "test-hook",
    "unexpected-seed",
    "unit-test",
    "missing-invocation",
)


@pytest.mark.parametrize("mutation", GRAPH_MUTATIONS)
def test_invalid_preflight_graph_prevents_live_subprocess(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    calls = []

    def parse_only(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(args[4])
        assert args[4] == "parse"
        manifest = _manifest()
        _mutate_graph(manifest, mutation)
        _write_artifacts(Path(args[args.index("--target-path") + 1]), manifest)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reconstruction.subprocess, "run", parse_only)
    with pytest.raises(DbtError):
        _run(settings_root)
    assert calls == ["parse"]


@pytest.mark.parametrize("command", ["build", "test"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "duplicate",
        "failed",
        "warning",
        "skipped",
        "nonzero-failures",
        "invocation",
        "graph-drift",
        "local-macro-drift",
    ],
)
def test_zero_exit_with_incomplete_duplicate_failed_or_stale_results_is_rejected(
    repo_root: Path,
    settings_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    mutation: str,
) -> None:
    def incomplete(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        phase = args[4]
        manifest = _manifest("synthetic-" + phase)
        results = None if phase == "parse" else _results(manifest, command)
        if results is not None:
            if mutation == "missing":
                results["results"].pop()
            elif mutation == "extra":
                results["results"].append(
                    {"unique_id": "test.commercelens.extra", "status": "pass", "failures": 0}
                )
            elif mutation == "duplicate":
                results["results"].append(copy.deepcopy(results["results"][0]))
            elif mutation in {"failed", "warning", "skipped"}:
                result = next(row for row in results["results"] if row["status"] == "pass")
                result["status"] = {"failed": "fail", "warning": "warn", "skipped": "skipped"}[
                    mutation
                ]
            elif mutation == "nonzero-failures":
                result = next(row for row in results["results"] if row["status"] == "pass")
                result["failures"] = 1
            elif mutation == "invocation":
                results["metadata"]["invocation_id"] = "different-invocation"
            elif mutation == "graph-drift":
                manifest["nodes"]["model.commercelens.stg_customers"]["raw_code"] = "select 2"
            else:
                manifest["macros"]["macro.commercelens.commercelens_nullable_money"][
                    "macro_sql"
                ] += " changed"
        _write_artifacts(Path(args[args.index("--target-path") + 1]), manifest, results)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reconstruction.subprocess, "run", incomplete)
    with pytest.raises(DbtError):
        _run(settings_root, command)


@pytest.mark.parametrize("phase", ["parse", "build"])
def test_success_exit_without_required_artifact_files_is_rejected(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    calls = []

    def missing_files(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        command = args[4]
        calls.append(command)
        if command != phase:
            _write_artifacts(Path(args[args.index("--target-path") + 1]), _manifest())
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reconstruction.subprocess, "run", missing_files)
    with pytest.raises(DbtError):
        _run(settings_root)
    assert calls == (["parse"] if phase == "parse" else ["parse", "build"])


@pytest.mark.parametrize("phase", ["parse", "build"])
@pytest.mark.parametrize("failure", ["returncode", "timeout", "oserror", "valueerror"])
def test_subprocess_failure_is_secret_safe_and_preserves_partial_artifacts(
    repo_root: Path,
    settings_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    phase: str,
    failure: str,
) -> None:
    retained = []

    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        command = args[4]
        target = Path(args[args.index("--target-path") + 1])
        if command != phase:
            _write_artifacts(target, _manifest())
            return subprocess.CompletedProcess(args, 0)
        target.mkdir(parents=True, exist_ok=True)
        marker = target / "partial-proof.txt"
        marker.write_text("retained", encoding="utf-8")
        retained.append(marker)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"], output=SECRET, stderr=SECRET)
        if failure == "oserror":
            raise OSError(SECRET)
        if failure == "valueerror":
            raise ValueError(SECRET)
        return subprocess.CompletedProcess(args, 2, stdout=SECRET, stderr=SECRET)

    monkeypatch.setattr(reconstruction.subprocess, "run", fail)
    with pytest.raises(DbtError) as error:
        _run(settings_root)
    output = capsys.readouterr()
    assert SECRET not in str(error.value) + output.out + output.err
    if failure in {"timeout", "oserror", "valueerror"}:
        assert error.value.__suppress_context__
    assert len(retained) == 1 and retained[0].read_text("utf-8") == "retained"


def test_real_offline_parse_of_unmodified_graph_has_no_network_or_private_settings(
    repo_root: Path, settings_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("dbt.cli.main")
    pytest.importorskip("psycopg2")
    actual_run = subprocess.run
    marker = repo_root / "network-attempt.txt"
    live_commands = []
    guard = (
        "import pathlib, runpy, socket, sys, psycopg2\n"
        f"marker=pathlib.Path({str(marker)!r})\n"
        "def forbidden(*args, **kwargs):\n"
        "    marker.write_text('blocked')\n"
        "    raise RuntimeError('Network is forbidden in offline reconstruction parsing')\n"
        "socket.socket.connect=forbidden\n"
        "socket.create_connection=forbidden\n"
        "psycopg2.connect=forbidden\n"
        "sys.argv[0]='dbt'\n"
        "runpy.run_module('dbt.cli.main', run_name='__main__')\n"
    )

    def parse_then_simulate(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        target = Path(args[args.index("--target-path") + 1])
        if args[4] == "parse":
            assert kwargs["env"]["DBT_ENV_SECRET_WAREHOUSE_PASSWORD"] != SECRET
            return actual_run([args[0], "-I", "-c", guard, *args[4:]], **kwargs)
        # Never dispatch build/test: preserve the real graph and simulate only
        # its result evidence so the public runner's preflight path is exercised.
        live_commands.append(args[4])
        preflight = next(
            (settings_root / ".artifacts/dbt-reconstruction").glob(
                "*/preflight/target/manifest.json"
            )
        )
        manifest = json.loads(preflight.read_text("utf-8"))
        manifest["metadata"]["invocation_id"] = "offline-simulated-build"
        _write_artifacts(target, manifest, _results(manifest, args[4]))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(reconstruction.subprocess, "run", parse_then_simulate)
    result = _run(settings_root)
    assert result["status"] == "passed"
    assert result["models"] == 21
    assert result["tests"] == 292
    assert live_commands == ["build"] and not marker.exists()
    manifests = list((settings_root / ".artifacts/dbt-reconstruction").rglob("manifest.json"))
    assert len(manifests) == 2
    for path in manifests:
        manifest = json.loads(path.read_text("utf-8"))
        models = {
            node["name"] for node in manifest["nodes"].values() if node["resource_type"] == "model"
        }
        assert models == set(MODEL_SCHEMAS)
        assert len(manifest["sources"]) == 9
        assert result["tests"] == sum(
            node["resource_type"] == "test" for node in manifest["nodes"].values()
        )
    for path in (settings_root / ".artifacts/dbt-reconstruction").rglob("*"):
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes()
            assert b"offline-parse-synthetic-password" not in path.read_bytes()
