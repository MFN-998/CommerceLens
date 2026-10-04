"""Offline routing and failure checks for an explicitly isolated reconstruction.

All connections, provisioning and source operations are simulated. Only small
synthetic configuration/artifact files are retained in the test workspace.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from src.warehouse import reconstruction
from src.warehouse.config import PURPOSE_FILES, PURPOSE_USERS, WarehouseSettings
from src.warehouse.credentials import ProvisioningError

PROJECT_REF = "abcdefghijklmnopqrst"
PROTECTED_REF = "imvahwzlovgmaltuysmb"
SECRET = "synthetic-reconstruction-detail-do-not-print"
STEPS = {
    "inspect": ("admin", "inspect_database"),
    "migrate": ("admin", "apply_migrations"),
    "verify": ("admin", "verify_privileges"),
    "provision-loader": ("admin", "provision_loader"),
    "provision-transformer": ("admin", "provision_transformer"),
    "load": ("loader", "load_source"),
    "grant-mart-reader": ("transformer", "grant_mart_reader"),
    "dbt-build-graph": ("transformer", "run_dbt_graph"),
    "dbt-test-graph": ("transformer", "run_dbt_graph"),
}


@pytest.fixture(autouse=True)
def no_ambient_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(reconstruction.os.environ):
        if name.upper().startswith(("WAREHOUSE_", "PG")):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(reconstruction, "ROOT", repo)

    def create(step: str = "inspect") -> SimpleNamespace:
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        (isolated / "ca.crt").write_text("synthetic public CA placeholder", encoding="utf-8")
        purpose = STEPS[step][0]
        private_file = isolated / PURPOSE_FILES[purpose]
        private_file.write_text("synthetic settings placeholder", encoding="utf-8")
        state = SimpleNamespace(
            repo=repo,
            isolated=isolated,
            private_file=private_file,
            events=[],
            calls=[],
            connection=object(),
            plan=object(),
            migrations=["synthetic-0001", "synthetic-0002"],
            close_failure=False,
            connect_failure=False,
            helper_failure=None,
            protection_failure=False,
        )
        state.settings = WarehouseSettings.model_validate(
            {
                "purpose": purpose,
                "environment": "test",
                "project_ref": PROJECT_REF,
                "host": f"db.{PROJECT_REF}.supabase.co",
                "user": PURPOSE_USERS[purpose],
                "password": SECRET,
                "sslrootcert": Path("ca.crt"),
            }
        )

        def protect(path: Path) -> None:
            state.events.append("protect")
            assert path == private_file
            if state.protection_failure:
                raise OSError(SECRET)

        def settings(root: Path, *, purpose: str) -> WarehouseSettings:
            state.events.append("settings")
            assert root == isolated and purpose == STEPS[step][0]
            return state.settings

        @contextmanager
        def connection(settings: WarehouseSettings):
            state.events.append("connect")
            state.connected_settings = settings
            if state.connect_failure:
                raise psycopg.OperationalError(SECRET)
            yield state.connection
            state.events.append("close")
            if state.close_failure:
                raise psycopg.OperationalError(SECRET)

        def helper(name: str):
            def call(*args: object, **kwargs: object):
                state.events.append(name)
                state.calls.append((name, args, kwargs))
                if state.helper_failure == name:
                    raise psycopg.OperationalError(SECRET)
                if name == "prepare_source":
                    return state.plan
                if name == "read_migrations":
                    return state.migrations
                if name == "apply_migrations":
                    return ["0001", "0002"]
                if name == "verify_privileges":
                    return None
                if name == "inspect_database":
                    return {
                        "database_bytes": 10_000_000,
                        "default_acl_count": 2,
                        "schemas": dict.fromkeys(
                            ("ops", "raw", "staging", "core", "marts"), "owner"
                        ),
                        "capability_roles": ["owner", "loader", "transformer", "reader"],
                        "tls_in_use": True,
                        "private_detail": SECRET,
                    }
                if name in {"provision_loader", "provision_transformer"}:
                    target = "loader" if name == "provision_loader" else "transformer"
                    (isolated / PURPOSE_FILES[target]).write_text(
                        "new synthetic credential", encoding="utf-8"
                    )
                    return {"role": PURPOSE_USERS[target], "credential_file": PURPOSE_FILES[target]}
                if name == "load_source":
                    return {
                        "status": "loaded",
                        "rows": 1_550_922,
                        "raw_bytes": 275_750_912,
                        "database_bytes": 287_026_323,
                        "private_detail": SECRET,
                    }
                if name == "grant_mart_reader":
                    return {
                        "status": "granted",
                        "model": "marts.mart_order_components",
                        "capability": "SELECT",
                        "private_detail": SECRET,
                    }
                artifacts = isolated / ".artifacts/dbt-reconstruction/synthetic"
                artifacts.mkdir(parents=True)
                return {
                    "models": 20,
                    "tests": 282,
                    "artifacts": str(artifacts),
                    "private_detail": SECRET,
                }

            return call

        monkeypatch.setattr(reconstruction, "protect_credential_file", protect)
        monkeypatch.setattr(reconstruction, "load_settings", settings)
        monkeypatch.setattr(reconstruction, "connect", connection)
        for name in (
            "inspect_database",
            "read_migrations",
            "apply_migrations",
            "verify_privileges",
            "provision_loader",
            "provision_transformer",
            "prepare_source",
            "load_source",
            "grant_mart_reader",
            "run_dbt_graph",
        ):
            monkeypatch.setattr(reconstruction, name, helper(name))
        return state

    return create


def _run(state: SimpleNamespace, step: str = "inspect", expected_ref: str = PROJECT_REF) -> dict:
    return reconstruction.run_reconstruction_step(
        step, settings_root=state.isolated, expected_project_ref=expected_ref
    )


@pytest.mark.parametrize("step", tuple(STEPS))
def test_each_fixed_step_routes_only_its_correct_purpose_and_code_or_settings_root(
    harness, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    state = harness(step)
    purpose, operation = STEPS[step]
    result = _run(state, step)
    assert result["step"] == step and result["project_ref"] == PROJECT_REF
    assert result["status"] == "passed" and SECRET not in json.dumps(result)
    assert capsys.readouterr().out == ""
    assert state.events[:2] == ["protect", "settings"]
    calls = {name: (args, kwargs) for name, args, kwargs in state.calls}
    assert operation in calls
    assert len([name for name, _, _ in state.calls if name == operation]) == 1
    if step.startswith("provision-"):
        args, kwargs = calls[operation]
        assert args[0].purpose == "admin" and kwargs == {"root": state.isolated}
        settings = args[0]
        assert "connect" not in state.events
    elif step.startswith("dbt-"):
        args, kwargs = calls[operation]
        assert args == ("build" if step == "dbt-build-graph" else "test",)
        assert kwargs == {"settings_root": state.isolated, "expected_project_ref": PROJECT_REF}
        assert "connect" not in state.events
        return
    else:
        settings = state.connected_settings
        assert state.events.index("protect") < state.events.index("connect")
        assert state.events.index(operation) < state.events.index("close")
        assert calls[operation][0][0] is state.connection
    assert settings.purpose == purpose and settings.sslrootcert == state.isolated / "ca.crt"
    assert settings.sslrootcert.is_absolute()
    assert state.settings.sslrootcert == Path("ca.crt")
    if step == "migrate":
        assert calls["read_migrations"][0] == (state.repo / "warehouse/migrations",)
        assert calls[operation][0] == (state.connection, state.migrations)
    if step == "load":
        assert calls["prepare_source"][0] == (state.repo,)
        assert state.events.index("prepare_source") < state.events.index("connect")
        assert calls[operation][0] == (state.connection, state.repo, state.plan)
    if step == "grant-mart-reader":
        assert calls[operation][1] == {"root": state.repo}


@pytest.mark.parametrize("step", ["rehearse", "pipeline", "reset", "dbt-build", "inspect other"])
def test_unsupported_steps_fail_before_private_files_or_helpers(harness, step: str) -> None:
    state = harness()
    with pytest.raises(reconstruction.ReconstructionError):
        _run(state, step)
    assert state.events == []


@pytest.mark.parametrize("reference", [PROTECTED_REF, "", "short", "A" * 20, "a" * 21])
def test_invalid_or_protected_reference_fails_before_private_files_or_helpers(
    harness, reference: str
) -> None:
    state = harness()
    with pytest.raises(reconstruction.ReconstructionError):
        _run(state, expected_ref=reference)
    assert state.events == []


@pytest.mark.parametrize(
    "name", ["WAREHOUSE_PASSWORD", "warehouse_host", "PGHOSTADDR", "PGSERVICE", "pguser"]
)
def test_ambient_routing_variables_fail_before_private_files_or_helpers(
    harness, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    state = harness()
    monkeypatch.setenv(name, SECRET)
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state)
    assert SECRET not in str(error.value) and state.events == []


@pytest.mark.parametrize("location", ["repo", "inside-repo", "parent-repo", "missing", "file"])
def test_settings_root_cannot_overlap_repository_or_be_missing_or_not_a_directory(
    harness, location: str
) -> None:
    state = harness()
    paths = {
        "repo": state.repo,
        "inside-repo": state.repo / "inside",
        "parent-repo": state.repo.parent,
        "missing": state.isolated / "missing",
        "file": state.private_file,
    }
    (state.repo / "inside").mkdir()
    with pytest.raises(reconstruction.ReconstructionError):
        reconstruction.run_reconstruction_step(
            "inspect", settings_root=paths[location], expected_project_ref=PROJECT_REF
        )
    assert state.events == []


def test_loader_file_missing_does_not_fall_back_to_available_administration_settings(
    harness,
) -> None:
    state = harness("inspect")
    with pytest.raises(reconstruction.ReconstructionError):
        _run(state, "load")
    assert state.events == [] and state.private_file.is_file()


@pytest.mark.parametrize(
    "updates",
    [
        {"purpose": "admin"},
        {"environment": "development"},
        {"project_ref": PROTECTED_REF},
        {"project_ref": "zyxwvutsrqponmlkjihg"},
        {"sslrootcert": Path("missing.crt")},
        {"sslrootcert": Path("../outside.crt")},
    ],
)
def test_bad_loaded_settings_or_certificate_fail_before_native_helpers(
    harness, updates: dict
) -> None:
    state = harness("load")
    (state.isolated.parent / "outside.crt").write_text("synthetic public CA", encoding="utf-8")
    state.settings = state.settings.model_copy(update=updates)
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state, "load")
    assert "connect" not in state.events and state.calls == []
    assert SECRET not in str(error.value)


def test_private_file_protection_failure_prevents_reading_settings_or_connecting(harness) -> None:
    state = harness()
    state.protection_failure = True
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state)
    assert state.events == ["protect"] and state.private_file.is_file()
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("target", ["existing", "escaped"])
def test_generated_credential_path_is_reviewed_before_provisioning(
    harness, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    state = harness("provision-loader")
    path = state.isolated / PURPOSE_FILES["loader"]
    if target == "existing":
        path.write_text("retained original credential", encoding="utf-8")
    else:
        original_resolve = Path.resolve

        def escaped_resolve(candidate: Path, *args: object, **kwargs: object) -> Path:
            if candidate == path:
                return state.isolated.parent / "outside-credential"
            return original_resolve(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", escaped_resolve)
    with pytest.raises(reconstruction.ReconstructionError):
        _run(state, "provision-loader")
    assert not any(name == "provision_loader" for name, _, _ in state.calls)
    if target == "existing":
        assert path.read_text("utf-8") == "retained original credential"


def test_source_preparation_failure_never_opens_loader_connection(harness) -> None:
    state = harness("load")
    state.helper_failure = "prepare_source"
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state, "load")
    assert "connect" not in state.events
    assert [name for name, _, _ in state.calls] == ["prepare_source"]
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("phase", ["connect", "helper", "close"])
def test_native_failures_are_silent_safe_and_never_retry_or_return_success(
    harness, capsys: pytest.CaptureFixture[str], phase: str
) -> None:
    state = harness("load")
    state.connect_failure = phase == "connect"
    state.close_failure = phase == "close"
    state.helper_failure = "load_source" if phase == "helper" else None
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state, "load")
    output = capsys.readouterr()
    assert SECRET not in str(error.value) + output.out + output.err
    assert output.out == "" and output.err == ""
    assert state.events.count("connect") == 1 and state.events.count("load_source") <= 1
    assert error.value.__suppress_context__


def test_provisioning_partial_file_is_retained_on_uncertain_failure_without_retry(
    harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = harness("provision-transformer")
    partial = state.isolated / PURPOSE_FILES["transformer"]
    calls = []

    def uncertain(settings: WarehouseSettings, *, root: Path) -> None:
        calls.append((settings, root))
        partial.write_text("retained partial evidence", encoding="utf-8")
        raise ProvisioningError(SECRET)

    monkeypatch.setattr(reconstruction, "provision_transformer", uncertain)
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state, "provision-transformer")
    assert len(calls) == 1 and calls[0][1] == state.isolated
    assert partial.read_text("utf-8") == "retained partial evidence"
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("failure", [False, True])
def test_cli_reports_success_only_after_clean_native_context_exit(
    harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: bool
) -> None:
    state = harness("load")
    state.close_failure = failure
    monkeypatch.setattr(
        "sys.argv",
        [
            "warehouse-reconstruction",
            "load",
            "--settings-root",
            str(state.isolated),
            "--expected-project-ref",
            PROJECT_REF,
        ],
    )
    assert reconstruction.main() == (1 if failure else 0)
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    if failure:
        assert output.out == ""
    else:
        assert state.events[-1] == "close"
        result = json.loads(output.out)
        assert result["status"] == "passed" and result["step"] == "load"


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["pipeline"],
        ["inspect", "--select", SECRET],
        ["inspect"],
        ["inspect", "--settings-root"],
    ],
)
def test_cli_rejects_missing_or_unapproved_arguments_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    monkeypatch.setattr(
        reconstruction, "run_reconstruction_step", lambda *a, **kw: pytest.fail("Dispatched")
    )
    monkeypatch.setattr("sys.argv", ["warehouse-reconstruction", *arguments])
    assert reconstruction.main() == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err.strip() == reconstruction.FAILURE_MESSAGE
    assert SECRET not in output.err


def test_graph_receipt_artifacts_cannot_escape_isolated_settings_root(
    harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = harness("dbt-build-graph")
    calls = []

    def outside_artifacts(*args: object, **kwargs: object) -> dict:
        calls.append((args, kwargs))
        return {"models": 20, "tests": 282, "artifacts": str(state.repo / SECRET)}

    monkeypatch.setattr(reconstruction, "run_dbt_graph", outside_artifacts)
    with pytest.raises(reconstruction.ReconstructionError) as error:
        _run(state, "dbt-build-graph")
    assert len(calls) == 1 and "connect" not in state.events
    assert SECRET not in str(error.value)


def test_cli_interrupt_is_safe_and_never_reports_success(
    harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = harness()

    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(reconstruction, "run_reconstruction_step", interrupted)
    monkeypatch.setattr(
        "sys.argv",
        [
            "warehouse-reconstruction",
            "inspect",
            "--settings-root",
            str(state.isolated),
            "--expected-project-ref",
            PROJECT_REF,
        ],
    )
    assert reconstruction.main() == 130
    output = capsys.readouterr()
    assert output.out == "" and SECRET not in output.err


def test_hard_linked_outside_credentials_are_rejected_before_permission_changes(
    harness,
) -> None:
    state = harness()
    # Keep both links and original content; no project-resource deletion is needed.
    outside_alias = state.isolated.parent / "outside-synthetic-credential"
    outside_alias.hardlink_to(state.private_file)
    before = outside_alias.read_bytes()
    assert state.private_file.stat().st_nlink > 1
    with pytest.raises(reconstruction.ReconstructionError):
        _run(state)
    assert state.events == []
    assert outside_alias.read_bytes() == before
    assert state.private_file.read_bytes() == before
