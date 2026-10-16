"""Offline proof that all Q01 database stages share the supervised deadline."""

from __future__ import annotations

import json
from contextlib import nullcontext

import pytest
from test_phase5_measurement import clock as clock
from test_phase5_query import request

from scripts import phase5_native as native
from src.analytics.measurement import Deadline, MeasurementError


@pytest.mark.parametrize("failure", [None, "before", "access", "queries", "after", "identity"])
def test_cli_keeps_every_database_stage_inside_supervisor(
    tmp_path, monkeypatch, capsys, clock, failure
):
    active = False
    stages = []
    deadline = Deadline(60)
    monkeypatch.setattr(native, "ROOT", tmp_path)
    monkeypatch.setattr(native, "_isolated_root", lambda *args: tmp_path)
    monkeypatch.setattr(native, "_settings", lambda root, purpose, reference: purpose)
    monkeypatch.setattr(native, "connect", lambda *args, **kwargs: pytest.fail("Unscoped DB"))

    def stage(name, settings, received):
        assert active and settings == "admin" and received is deadline
        received.check()
        stages.append(name)
        if name == failure:
            raise RuntimeError("synthetic-private-driver-detail")

    def metadata(settings, received):
        name = "after" if "before" in stages else "before"
        stage(name, settings, received)
        return {"relations": [name] if failure == "identity" else [], "raw_bytes": 1}

    def access(settings, received):
        stage("access", settings, received)

    def queries(settings, folder, received):
        stage("queries", settings, received)
        return {"q01": "passed_bounded_development"}

    def supervise(work, settings, folder):
        nonlocal active
        assert work is native._measurement_job
        assert work.__qualname__ == "_measurement_job"
        active = True
        try:
            return work(settings, folder, deadline)
        finally:
            active = False

    monkeypatch.setattr(native, "metadata", metadata)
    monkeypatch.setattr(native, "verify_access", access)
    monkeypatch.setattr(native, "_measure_queries", queries)
    monkeypatch.setattr(native, "run_bounded_measurement", supervise)
    monkeypatch.setattr(
        "sys.argv",
        [
            "native",
            "measure",
            "--settings-root",
            str(tmp_path),
            "--expected-project-ref",
            "a" * 20,
        ],
    )
    assert native.main() == int(failure is not None)
    assert not active
    output = capsys.readouterr()
    assert "synthetic-private-driver-detail" not in output.out + output.err
    folder = next((tmp_path / ".artifacts/phase-5").iterdir())
    if failure:
        receipt = json.loads((folder / "failure.json").read_text())
        assert receipt["stage"] == "measure"
        assert receipt["build_attempted"] is receipt["grant_attempted"] is False
        assert receipt["recovery"] == "Inspect retained measurement stages before retry"
        detail = json.loads((folder / "measurement-failure.json").read_text())
        assert detail == {
            "status": "failed",
            "stage": "after" if failure == "identity" else failure,
            "private_detail_logged": False,
        }
        assert not (folder / "receipt.json").exists()
    else:
        assert stages == ["before", "access", "queries", "after"]
        assert (folder / "before.json").is_file() and (folder / "after.json").is_file()
        assert len(list(folder.glob("measurement-*-started.json"))) == 4


class Denied(Exception):
    sqlstate = "42501"


class Connection:
    def __init__(self, clock, calls, expire_on=None):
        self.clock = clock
        self.calls = calls
        self.expire_on = expire_on
        self.statement = ""
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        if self.expire_on == "close":
            self.clock.now = 61

    def transaction(self, **kwargs):
        return nullcontext()

    def execute(self, statement, parameters=None, **kwargs):
        self.statement = statement
        self.calls.append(statement)
        self.clock.now += 0.01
        if statement.startswith("select 1 from"):
            raise Denied()
        if statement == "catalog" and self.expire_on == "catalog":
            self.clock.now = 61
        return self

    def fetchone(self):
        if "pg_database_size" in self.statement:
            return (100, 10)
        if "rolcanlogin" in self.statement:
            return (False,) * 7
        if "has_table_privilege('commercelens_reader'" in self.statement:
            return (True, False)
        if self.statement.startswith("EXPLAIN"):
            if self.expire_on == "plan":
                self.clock.now = 61
            return ([{}],)
        if "block_size" in self.statement:
            if self.expire_on == "block":
                self.clock.now = 61
            return (8192,)
        return (0,)

    def fetchall(self):
        if self.expire_on == "relations":
            self.clock.now = 61
        return []


@pytest.fixture
def driver(monkeypatch, clock):
    state = {"calls": [], "options": [], "connections": [], "expire_on": None}

    def connect(settings, **options):
        state["options"].append(options)
        connection = Connection(clock, state["calls"], state["expire_on"])
        state["connections"].append(connection)
        return connection

    monkeypatch.setattr(native, "connect", connect)
    monkeypatch.setattr(native, "verify_reader_catalog", lambda c: c.execute("catalog"))
    return state


@pytest.mark.parametrize("bounded", [False, True])
def test_metadata_access_and_reader_defaults_or_shared_limits(driver, clock, monkeypatch, bounded):
    deadline = Deadline(60) if bounded else None
    received = []

    def fetch(connection, query, *, deadline):
        received.append(deadline)
        return {"rows": []}

    monkeypatch.setattr(native, "fetch_metrics", fetch)
    native.metadata("admin", deadline)
    native.verify_access("admin", deadline)
    native.read_query("admin", request(), deadline)
    assert received == [deadline]
    assert all(connection.closed for connection in driver["connections"])
    if bounded:
        assert all(options["connect_timeout"] == 10 for options in driver["options"])
        assert all(0 < options["statement_timeout_ms"] <= 55000 for options in driver["options"])
        catalog = driver["calls"].index("catalog")
        assert driver["calls"][catalog - 1].startswith("SET statement_timeout=")
        assert any(statement.startswith("SET lock_timeout=") for statement in driver["calls"])
    else:
        assert driver["options"] == [{}, {}, {}]
        assert not any("timeout=" in statement for statement in driver["calls"])


@pytest.mark.parametrize("failure", ["relations", "catalog", "close"])
def test_nonquery_stages_expire_and_close_connections(driver, clock, monkeypatch, failure):
    driver["expire_on"] = failure
    monkeypatch.setattr(native, "fetch_metrics", lambda *args, **kwargs: {"rows": []})
    with pytest.raises(MeasurementError):
        if failure == "relations":
            native.metadata("admin", Deadline(60))
        elif failure == "catalog":
            native.verify_access("admin", Deadline(60))
        else:
            native.read_query("admin", request(), Deadline(60))
    assert all(connection.closed for connection in driver["connections"])


@pytest.mark.parametrize("failure", [None, "plan", "block", "concurrency"])
def test_query_plan_metadata_and_concurrent_reads_use_one_deadline(
    driver, clock, tmp_path, monkeypatch, failure
):
    driver["expire_on"] = failure
    deadline = Deadline(60)
    reads = []
    monkeypatch.setattr(native, "cases", lambda: [("one", request()), ("two", request())])
    monkeypatch.setattr(
        native,
        "summarize_plan",
        lambda plan: {
            "execution_ms": 1,
            "root_buffers": {"Temp Read Blocks": 0, "Temp Written Blocks": 0},
        },
    )

    def read(settings, query, received):
        assert received is deadline
        reads.append(received)
        if failure == "concurrency" and len(reads) > 2:
            clock.now = 61
        received.check()
        return {"rows": []}, {"seconds": 0.1, "bytes": 2, "rows": 0, "sha256": "synthetic"}

    monkeypatch.setattr(native, "read_query", read)
    if failure:
        with pytest.raises(MeasurementError):
            native._measure_queries("admin", tmp_path, deadline)
        if failure == "plan":
            assert not any("block_size" in statement for statement in driver["calls"])
        if failure == "concurrency":
            assert (tmp_path / "one.json").is_file() and (tmp_path / "two.json").is_file()
    else:
        result = native._measure_queries("admin", tmp_path, deadline)
        assert result["q01"] == "passed_bounded_development"
        assert len(reads) == 4 and len(result["concurrent"]) == 2
    assert all(connection.closed for connection in driver["connections"])
    assert all(options["statement_timeout_ms"] <= 55000 for options in driver["options"])
