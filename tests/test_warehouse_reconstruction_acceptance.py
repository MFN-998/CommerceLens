"""Offline coverage and routing proof for isolated reconstruction acceptance.

Pytest items, reports and subprocesses are synthetic. These tests do not execute
the accepted integration SQL or connect to a warehouse.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.warehouse import reconstruction
from src.warehouse import reconstruction_acceptance as acceptance
from src.warehouse.config import PURPOSE_FILES, PURPOSE_USERS, WarehouseSettings

PROJECT_REF = "abcdefghijklmnopqrst"
SECRET = "synthetic-private-acceptance-detail"
PHYSICAL_FILES = frozenset(
    {
        "test_warehouse_category_translation_integration.py",
        "test_warehouse_customer_integration.py",
        "test_warehouse_customer_dimension_integration.py",
        "test_warehouse_date_dimension_integration.py",
        "test_warehouse_geolocation_integration.py",
        "test_warehouse_item_integration.py",
        "test_warehouse_location_integration.py",
        "test_warehouse_order_integration.py",
        "test_warehouse_payment_integration.py",
        "test_warehouse_product_integration.py",
        "test_warehouse_product_dimension_integration.py",
        "test_warehouse_review_integration.py",
        "test_warehouse_seller_integration.py",
        "test_warehouse_seller_dimension_integration.py",
        "test_warehouse_order_customers_integration.py",
        "test_warehouse_fact_orders_integration.py",
        "test_warehouse_fact_order_items_integration.py",
        "test_warehouse_fact_payments_integration.py",
        "test_warehouse_fact_reviews_integration.py",
        "test_warehouse_order_components_integration.py",
    }
)
APPROVED_FILES = PHYSICAL_FILES | {
    "test_warehouse_query_examples_postgres_integration.py",
    "test_warehouse_mart_reader_integration.py",
}


@pytest.fixture(autouse=True)
def no_ambient_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(acceptance.os.environ):
        if name.upper().startswith(("WAREHOUSE_", "PG")):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    repo, isolated = tmp_path / "repo", tmp_path / "isolated"
    repo.mkdir()
    isolated.mkdir()
    (isolated / "ca.crt").write_text("synthetic public CA", encoding="utf-8")
    state = SimpleNamespace(repo=repo, isolated=isolated, events=[], calls=[])
    state.settings = {}
    for purpose in ("admin", "transformer"):
        (isolated / PURPOSE_FILES[purpose]).write_text("synthetic settings", encoding="utf-8")
        state.settings[purpose] = WarehouseSettings.model_validate(
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
        state.events.append(("protect", path.name))
        assert path.parent == isolated

    def settings(root: Path, *, purpose: str) -> WarehouseSettings:
        state.events.append(("settings", purpose))
        assert root == isolated
        return state.settings[purpose]

    monkeypatch.setattr(acceptance, "ROOT", repo)
    monkeypatch.setattr(reconstruction, "ROOT", repo)
    monkeypatch.setattr(reconstruction, "protect_credential_file", protect)
    monkeypatch.setattr(reconstruction, "load_settings", settings)
    return state


def _item(target: SimpleNamespace, filename: str, *, fixtures: tuple[str, ...] = ()):
    path = target.repo / "tests" / filename
    path.parent.mkdir(exist_ok=True)
    path.touch()
    module = SimpleNamespace(
        __file__=str(path),
        load_settings=object(),
        connect=object(),
        transformer_connection=object(),
        synthetic_sql="SELECT 'literal fixture remains unchanged'",
    )
    return SimpleNamespace(
        nodeid="tests/" + filename + "::test_synthetic",
        path=path,
        module=module,
        fixturenames=fixtures,
    )


def _report(nodeid: str, when: str = "call", outcome: str = "passed") -> SimpleNamespace:
    return SimpleNamespace(
        nodeid=nodeid,
        when=when,
        outcome=outcome,
        passed=outcome == "passed",
        failed=outcome == "failed",
        skipped=outcome == "skipped",
        longrepr=SECRET,
    )


def _items(target: SimpleNamespace) -> list[SimpleNamespace]:
    return [_item(target, filename) for filename in sorted(APPROVED_FILES)]


def _plugin(target: SimpleNamespace):
    receipt = target.isolated / "synthetic-receipt.json"
    return acceptance._AcceptancePlugin(target.isolated, PROJECT_REF, receipt), receipt


def _passed_receipt() -> dict:
    return {
        "status": "passed",
        "project_ref": PROJECT_REF,
        "files": dict.fromkeys(APPROVED_FILES, 1),
        "collected": 22,
        "passed": 22,
        "errors": 0,
    }


def _artifact_directory(target: SimpleNamespace) -> Path:
    directories = list((target.isolated / ".artifacts/reconstruction-acceptance").iterdir())
    assert len(directories) == 1
    return directories[0]


def test_parent_uses_fixed_bounded_worker_and_only_allowed_child_opt_ins(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _items(target)
    monkeypatch.setenv("COMMERCE_WAREHOUSE_LOADING_INTEGRATION", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", SECRET)
    monkeypatch.setenv("PYTEST_PLUGINS", SECRET)

    def worker(command: list[str], **kwargs: object) -> SimpleNamespace:
        target.calls.append((command, kwargs))
        folder = _artifact_directory(target)
        assert not (folder / "basetemp").exists()
        acceptance._write_receipt(folder / "receipt.json", _passed_receipt())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(acceptance.subprocess, "run", worker)
    result = acceptance.run_reconstruction_acceptance(
        settings_root=target.isolated, expected_project_ref=PROJECT_REF
    )
    assert len(target.calls) == 1
    command, options = target.calls[0]
    assert command[:3] == [sys.executable, "-I", "-B"]
    assert options["timeout"] == 600 and options["cwd"] == target.repo
    assert options["stdout"] == subprocess.DEVNULL and options["stderr"] == subprocess.DEVNULL
    environment = options["env"]
    expected_flags = {
        "COMMERCE_WAREHOUSE_"
        + (
            "FACT_ITEMS"
            if filename == "test_warehouse_fact_order_items_integration.py"
            else "QUERY_EXAMPLES"
            if filename == "test_warehouse_query_examples_postgres_integration.py"
            else filename.removeprefix("test_warehouse_").removesuffix("_integration.py").upper()
        )
        + "_INTEGRATION"
        for filename in APPROVED_FILES
    }
    actual_flags = {name for name in environment if name.upper().startswith("COMMERCE_WAREHOUSE_")}
    assert actual_flags == expected_flags and all(environment[name] == "1" for name in actual_flags)
    assert not any(name.upper().startswith(("WAREHOUSE_", "PG")) for name in environment)
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert "PYTEST_ADDOPTS" not in environment and "PYTEST_PLUGINS" not in environment
    assert SECRET not in json.dumps(environment)
    assert acceptance.os.environ["COMMERCE_WAREHOUSE_LOADING_INTEGRATION"] == "1"
    assert acceptance.os.environ["PYTEST_ADDOPTS"] == SECRET
    assert result == {**_passed_receipt(), "artifacts": str(_artifact_directory(target))}
    assert capsys.readouterr().out == ""
    assert [event for event in target.events if event[0] == "settings"] == [
        ("settings", "admin"),
        ("settings", "transformer"),
    ]


@pytest.mark.parametrize(
    "corruption",
    [
        "incomplete",
        "missing-file",
        "extra-file",
        "count-mismatch",
        "bool-count",
        "wrong-ref",
        "extra-key",
    ],
)
def test_zero_worker_exit_cannot_accept_incomplete_or_corrupt_coverage_receipt(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    _items(target)

    def worker(*args: object, **kwargs: object) -> SimpleNamespace:
        target.calls.append((args, kwargs))
        receipt = _passed_receipt()
        if corruption == "incomplete":
            receipt["status"] = "incomplete"
        elif corruption == "missing-file":
            receipt["files"].pop(next(iter(receipt["files"])))
        elif corruption == "extra-file":
            receipt["files"]["test_warehouse_loading_integration.py"] = 1
        elif corruption == "count-mismatch":
            receipt["passed"] -= 1
        elif corruption == "bool-count":
            receipt["files"][next(iter(receipt["files"]))] = True
        elif corruption == "wrong-ref":
            receipt["project_ref"] = "zyxwvutsrqponmlkjihg"
        else:
            receipt["unapproved_detail"] = 1
        acceptance._write_receipt(_artifact_directory(target) / "receipt.json", receipt)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(acceptance.subprocess, "run", worker)
    with pytest.raises(acceptance.ReconstructionAcceptanceError):
        acceptance.run_reconstruction_acceptance(
            settings_root=target.isolated, expected_project_ref=PROJECT_REF
        )
    assert len(target.calls) == 1 and (_artifact_directory(target) / "receipt.json").is_file()


@pytest.mark.parametrize("failure", ["startup", "encoding", "timeout", "exit"])
def test_worker_failure_is_safe_retains_partial_counts_and_never_retries(
    target: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    _items(target)

    def worker(*args: object, **kwargs: object) -> SimpleNamespace:
        target.calls.append((args, kwargs))
        if failure == "startup":
            raise OSError(SECRET)
        if failure == "encoding":
            raise ValueError(SECRET)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(SECRET, 600, output=SECRET, stderr=SECRET)
        receipt = {**_passed_receipt(), "status": "failed", "passed": 21, "errors": 1}
        acceptance._write_receipt(_artifact_directory(target) / "receipt.json", receipt)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(acceptance.subprocess, "run", worker)
    with pytest.raises(acceptance.ReconstructionAcceptanceError) as error:
        acceptance.run_reconstruction_acceptance(
            settings_root=target.isolated, expected_project_ref=PROJECT_REF
        )
    output = capsys.readouterr()
    assert len(target.calls) == 1 and output.out == "" and output.err == ""
    assert SECRET not in str(error.value) and error.value.__suppress_context__
    folder = _artifact_directory(target)
    receipt = json.loads((folder / "receipt.json").read_text("utf-8"))
    assert receipt["status"] != "passed"
    assert receipt["passed"] == (21 if failure == "exit" else 0)
    assert not any(SECRET in path.read_text("utf-8") for path in folder.iterdir() if path.is_file())


def test_fixed_allowlist_is_exactly_twenty_physical_models_query_native_and_reader() -> None:
    assert len(PHYSICAL_FILES) == 20 and len(APPROVED_FILES) == 22
    assert set(acceptance.TEST_FILES) == APPROVED_FILES
    assert len(acceptance.TEST_FILES) == 22 and acceptance.ACCEPTANCE_TIMEOUT_SECONDS == 600


def test_plugin_injects_only_local_settings_and_preserves_connections_and_full_coverage(
    target: SimpleNamespace,
) -> None:
    items = _items(target)
    original_globals = [vars(item.module).copy() for item in items]
    plugin, path = _plugin(target)
    plugin.pytest_collection_modifyitems(items)
    for item, original in zip(items, original_globals, strict=True):
        assert {
            key: value for key, value in vars(item.module).items() if key != "load_settings"
        } == {key: value for key, value in original.items() if key != "load_settings"}
        purpose = "admin" if "mart_reader" in item.nodeid else "transformer"
        settings = item.module.load_settings(purpose=purpose)
        assert settings.purpose == purpose and settings.project_ref == PROJECT_REF
        assert settings.sslrootcert == target.isolated / "ca.crt"
        assert settings.sslrootcert.is_absolute()
        assert target.settings[purpose].sslrootcert == Path("ca.crt")
        for when in ("setup", "call", "teardown"):
            plugin.pytest_runtest_logreport(_report(item.nodeid, when))
    plugin.pytest_sessionfinish(SimpleNamespace(exitstatus=0), 0)
    receipt = acceptance._verify_receipt(path, PROJECT_REF)
    assert receipt == {
        "status": "passed",
        "project_ref": PROJECT_REF,
        "files": dict.fromkeys(APPROVED_FILES, 1),
        "collected": 22,
        "passed": 22,
        "errors": 0,
    }
    assert SECRET not in path.read_text("utf-8")


@pytest.mark.parametrize(
    "corruption", ["missing-file", "extra-file", "duplicate-id", "outside-path", "temp-fixture"]
)
def test_collection_rejects_wrong_file_coverage_duplicate_ids_and_temporary_fixtures(
    target: SimpleNamespace, corruption: str
) -> None:
    items = _items(target)
    if corruption == "missing-file":
        items.pop()
    elif corruption == "extra-file":
        items.append(_item(target, "test_warehouse_loading_integration.py"))
    elif corruption == "duplicate-id":
        items.append(items[0])
    elif corruption == "outside-path":
        items[0].module.__file__ = str(target.isolated / Path(items[0].module.__file__).name)
    else:
        items[0].fixturenames = ("tmp_path",)
    plugin, path = _plugin(target)
    with pytest.raises(acceptance.ReconstructionAcceptanceError) as error:
        plugin.pytest_collection_modifyitems(items)
    assert SECRET not in str(error.value)
    if path.is_file():
        assert json.loads(path.read_text("utf-8"))["status"] != "passed"


@pytest.mark.parametrize("fixture", ["tmp_path", "tmp_path_factory"])
def test_dynamic_temporary_fixture_requests_are_rejected_before_creation(
    target: SimpleNamespace, fixture: str
) -> None:
    plugin, _ = _plugin(target)
    with pytest.raises(acceptance.ReconstructionAcceptanceError):
        plugin.pytest_fixture_setup(SimpleNamespace(argname=fixture), SimpleNamespace())
    assert plugin.pytest_fixture_setup(SimpleNamespace(argname="reader_connection"), None) is None


@pytest.mark.parametrize(
    "corruption",
    [
        "skipped-call",
        "failed-setup",
        "failed-teardown",
        "missing-call",
        "duplicate-call",
        "unknown-node",
        "xfail-call",
        "nonzero-exit",
    ],
)
def test_every_collected_node_requires_exact_setup_call_teardown_pass_reports(
    target: SimpleNamespace, corruption: str
) -> None:
    plugin, path = _plugin(target)
    items = _items(target)
    plugin.pytest_collection_modifyitems(items)
    for index, item in enumerate(items):
        for when in ("setup", "call", "teardown"):
            if index == 0 and corruption == "missing-call" and when == "call":
                continue
            outcome = "passed"
            if index == 0 and corruption == "skipped-call" and when == "call":
                outcome = "skipped"
            if index == 0 and corruption == "failed-" + when:
                outcome = "failed"
            report = _report(item.nodeid, when, outcome)
            if index == 0 and corruption == "xfail-call" and when == "call":
                report.wasxfail = SECRET
            plugin.pytest_runtest_logreport(report)
    if corruption == "duplicate-call":
        plugin.pytest_runtest_logreport(_report(items[0].nodeid))
    if corruption == "unknown-node":
        plugin.pytest_runtest_logreport(_report("tests/unknown.py::" + SECRET))
    exitstatus = 1 if corruption == "nonzero-exit" else 0
    session = SimpleNamespace(exitstatus=exitstatus)
    plugin.pytest_sessionfinish(session, exitstatus)
    assert json.loads(path.read_text("utf-8"))["status"] != "passed"
    assert SECRET not in path.read_text("utf-8")
    with pytest.raises(ValueError):
        acceptance._verify_receipt(path, PROJECT_REF)


def test_worker_invokes_only_fixed_files_with_capture_cache_conftest_and_reused_temp_disabled(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = _items(target)
    artifacts = target.isolated / ".artifacts/reconstruction-acceptance/synthetic-worker"
    artifacts.mkdir(parents=True)
    calls = []

    def run(arguments: list[str], *, plugins: list) -> int:
        calls.append(arguments)
        paths = [Path(argument) for argument in arguments if argument.endswith(".py")]
        assert {path.name for path in paths} == APPROVED_FILES and len(paths) == 22
        assert all(path.parent == target.repo / "tests" for path in paths)
        assert arguments[arguments.index("--rootdir") + 1] == str(target.repo)
        assert arguments[arguments.index("--basetemp") + 1] == str(artifacts / "basetemp")
        assert arguments[arguments.index("-o") + 1] == "addopts=-q"
        assert {"--noconftest", "no:cacheprovider", "--capture=no"}.issubset(arguments)
        assert not (artifacts / "basetemp").exists() and len(plugins) == 1
        plugin = plugins[0]
        plugin.pytest_collection_modifyitems(items)
        for item in items:
            for when in ("setup", "call", "teardown"):
                plugin.pytest_runtest_logreport(_report(item.nodeid, when))
        plugin.pytest_sessionfinish(SimpleNamespace(exitstatus=0), 0)
        return 0

    monkeypatch.setattr(acceptance.pytest, "main", run)
    assert acceptance._worker(target.isolated, PROJECT_REF, artifacts) == 0
    assert len(calls) == 1 and not (artifacts / "basetemp").exists()
    assert acceptance._verify_receipt(artifacts / "receipt.json", PROJECT_REF)["passed"] == 22


@pytest.mark.parametrize("existing", [True, False])
def test_worker_refuses_existing_or_symlink_basetemp_before_pytest_and_preserves_files(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    artifacts = target.isolated / ".artifacts/reconstruction-acceptance/synthetic-worker"
    artifacts.mkdir(parents=True)
    basetemp = artifacts / "basetemp"
    marker = artifacts / "retained-marker.txt"
    if existing:
        basetemp.mkdir()
        marker = basetemp / marker.name
    else:
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path, "is_symlink", lambda path: path == basetemp or original_is_symlink(path)
        )
    marker.write_text("retained evidence", encoding="utf-8")

    def unexpected_pytest(*args: object, **kwargs: object) -> None:
        pytest.fail("Pytest started with an unsafe existing temporary path")

    monkeypatch.setattr(acceptance.pytest, "main", unexpected_pytest)
    assert acceptance._worker(target.isolated, PROJECT_REF, artifacts) == 1
    assert marker.read_text("utf-8") == "retained evidence"


@pytest.mark.parametrize(
    "guard",
    ["protected-reference", "ambient-warehouse", "ambient-pg", "missing-file", "missing-ca"],
)
def test_parent_target_guards_run_before_subprocess(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, guard: str
) -> None:
    _items(target)
    reference = PROJECT_REF
    if guard == "protected-reference":
        reference = "imvahwzlovgmaltuysmb"
    elif guard.startswith("ambient-"):
        monkeypatch.setenv("pgservice" if guard == "ambient-pg" else "warehouse_host", SECRET)
    elif guard == "missing-file":
        original_is_file = Path.is_file
        private = target.isolated / PURPOSE_FILES["transformer"]
        monkeypatch.setattr(
            Path, "is_file", lambda path: path != private and original_is_file(path)
        )
    else:
        target.settings["transformer"] = target.settings["transformer"].model_copy(
            update={"sslrootcert": Path("missing.crt")}
        )

    def unexpected_worker(*args: object, **kwargs: object) -> None:
        pytest.fail("Target guard dispatched a worker")

    monkeypatch.setattr(acceptance.subprocess, "run", unexpected_worker)
    with pytest.raises(acceptance.ReconstructionAcceptanceError) as error:
        acceptance.run_reconstruction_acceptance(
            settings_root=target.isolated, expected_project_ref=reference
        )
    assert SECRET not in str(error.value) and error.value.__suppress_context__
    if guard in {"protected-reference", "ambient-warehouse", "ambient-pg"}:
        assert target.events == []


def test_cli_success_passes_explicit_target_and_prints_only_receipt(
    target: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = []
    receipt = {"complete": True, "tests": 22, "project_ref": PROJECT_REF}

    def run(**kwargs: object) -> dict:
        calls.append(kwargs)
        return receipt

    monkeypatch.setattr(acceptance, "run_reconstruction_acceptance", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "warehouse-reconstruction-acceptance",
            "--run",
            "--settings-root",
            str(target.isolated),
            "--expected-project-ref",
            PROJECT_REF,
        ],
    )
    assert acceptance.main() == 0
    assert calls == [{"settings_root": target.isolated, "expected_project_ref": PROJECT_REF}]
    output = capsys.readouterr()
    assert json.loads(output.out) == receipt and output.err == ""


@pytest.mark.parametrize("invalid", ["missing-opt-in", "arbitrary-selector", "private-worker"])
def test_cli_rejects_unapproved_arguments_without_echoing_or_dispatching(
    target: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invalid: str,
) -> None:
    arguments = [
        "--run",
        "--settings-root",
        str(target.isolated),
        "--expected-project-ref",
        PROJECT_REF,
    ]
    if invalid == "missing-opt-in":
        arguments.pop(0)
    else:
        arguments.extend(["--select" if invalid == "arbitrary-selector" else "--worker", SECRET])
    monkeypatch.setattr(
        acceptance, "run_reconstruction_acceptance", lambda **kwargs: pytest.fail("Dispatched")
    )
    monkeypatch.setattr("sys.argv", ["warehouse-reconstruction-acceptance", *arguments])
    assert acceptance.main() != 0
    output = capsys.readouterr()
    assert output.out == "" and output.err and SECRET not in output.err


@pytest.mark.parametrize("interrupted", [False, True])
def test_cli_failure_or_interrupt_never_prints_private_details_or_success(
    target: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    interrupted: bool,
) -> None:
    def fail(**kwargs: object) -> None:
        if interrupted:
            raise KeyboardInterrupt(SECRET)
        raise acceptance.ReconstructionAcceptanceError(SECRET)

    monkeypatch.setattr(acceptance, "run_reconstruction_acceptance", fail)
    monkeypatch.setattr(
        "sys.argv",
        [
            "warehouse-reconstruction-acceptance",
            "--run",
            "--settings-root",
            str(target.isolated),
            "--expected-project-ref",
            PROJECT_REF,
        ],
    )
    assert acceptance.main() == (130 if interrupted else 1)
    output = capsys.readouterr()
    assert output.out == "" and output.err and SECRET not in output.err
