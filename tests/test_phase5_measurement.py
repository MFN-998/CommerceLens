"""Offline deadline, timeout propagation, and child cleanup regressions."""

from __future__ import annotations

import json
import multiprocessing
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from test_phase5_query import Connection, raw, request

from src.analytics import measurement
from src.analytics.query import AnalyticsError, fetch_metrics
from src.warehouse.config import connect


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(measurement, "monotonic", value)
    return value


def test_connection_limits_shrink_without_libpq_rounding_past_deadline(clock):
    deadline = measurement.Deadline(10)
    assert deadline.connection_options() == {
        "connect_timeout": 10,
        "statement_timeout_ms": 10_000,
        "lock_timeout_ms": 5_000,
    }
    clock.now = 7.5
    assert deadline.connection_options() == {
        "connect_timeout": 2,
        "statement_timeout_ms": 2_500,
        "lock_timeout_ms": 2_500,
    }
    clock.now = 8.1
    with pytest.raises(measurement.MeasurementError, match="connection budget"):
        deadline.connection_options()


@pytest.mark.parametrize("stage", ["setup", "query", "fetch"])
def test_query_deadline_covers_setup_execution_and_fetch(clock, stage):
    class SlowConnection(Connection):
        def execute(self, sql, parameters=None, **kwargs):
            result = super().execute(sql, parameters, **kwargs)
            if (stage == "setup" and sql.startswith("SET lock")) or (
                stage == "query" and parameters is not None
            ):
                clock.now = 11
            return result

        def fetchmany(self, size):
            if stage == "fetch":
                clock.now = 11
            return super().fetchmany(size)

    connection = SlowConnection([tuple(raw().values())])
    with pytest.raises(AnalyticsError, match="no private detail"):
        fetch_metrics(connection, request(), deadline=measurement.Deadline(10))
    if stage == "setup":
        assert not any(parameters is not None for _, parameters in connection.calls)


def test_query_never_restores_fixed55_second_timeout(clock):
    connection = Connection([tuple(raw().values())])
    response = fetch_metrics(connection, request(), deadline=measurement.Deadline(3))
    assert response["rows"][0]["gmv"] == "0.00"
    statements = [statement for statement, _ in connection.calls]
    assert "SET statement_timeout='3000ms'" in statements
    assert "SET LOCAL statement_timeout='55s'" not in statements


def test_connection_preserves_tls_and_applies_stricter_limits(monkeypatch, tmp_path):
    from src.warehouse import config

    captured = {}
    monkeypatch.setattr(config.psycopg, "connect", lambda **kwargs: captured.update(kwargs))
    settings = SimpleNamespace(
        host="synthetic.invalid",
        port=5432,
        database="postgres",
        user="postgres",
        password=SimpleNamespace(get_secret_value=lambda: "synthetic-private"),
        certificate_path=lambda: tmp_path / "ca.crt",
        purpose="admin",
    )
    connect(settings, connect_timeout=2, statement_timeout_ms=2500, lock_timeout_ms=1000)
    assert captured["connect_timeout"] == 2
    assert captured["sslmode"] == "verify-full"
    assert captured["options"] == (
        "-c statement_timeout=2500 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=2500"
    )
    assert captured["autocommit"] is True


@pytest.mark.parametrize(
    "options",
    [
        {"connect_timeout": 1},
        {"connect_timeout": True},
        {"statement_timeout_ms": 0},
        {"statement_timeout_ms": 60001},
        {"statement_timeout_ms": 10, "lock_timeout_ms": 11},
    ],
)
def test_invalid_timeouts_fail_before_connection(options, monkeypatch):
    monkeypatch.setattr(
        "src.warehouse.config.psycopg.connect", lambda **kwargs: pytest.fail("connected")
    )
    with pytest.raises(ValueError, match="bounded warehouse"):
        connect(object(), **options)


def _never_finishes(settings, folder, deadline):
    sleep(30)
    return {}


def test_real_worker_timeout_reaps_process_and_its_threads(tmp_path):
    before = {process.pid for process in multiprocessing.active_children()}
    started = monotonic()
    with pytest.raises(measurement.MeasurementError, match="failed or expired"):
        measurement.run_bounded_measurement(_never_finishes, None, tmp_path, job_seconds=3)
    assert monotonic() - started < 4
    assert {process.pid for process in multiprocessing.active_children()} == before


@pytest.mark.parametrize("stubborn", [False, True])
def test_supervisor_reserves_cleanup_and_escalates_to_kill(clock, tmp_path, monkeypatch, stubborn):
    class Process:
        alive = True
        calls = []
        exitcode = None

        def start(self):
            self.calls.append("start")

        def join(self, timeout):
            self.calls.append(("join", timeout))
            if self.alive:
                clock.now += timeout

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.calls.append("terminate")
            if not stubborn:
                self.alive = False

        def kill(self):
            self.calls.append("kill")
            self.alive = False

        def close(self):
            self.calls.append("close")

    process = Process()
    monkeypatch.setattr(
        measurement.multiprocessing,
        "get_context",
        lambda method: SimpleNamespace(Process=lambda **kwargs: process),
    )
    with pytest.raises(measurement.MeasurementError):
        measurement.run_bounded_measurement(_never_finishes, None, tmp_path)
    assert ("join", 598) in process.calls
    assert "terminate" in process.calls and process.calls[-1] == "close"
    assert ("kill" in process.calls) is stubborn
    assert clock.now < 600 and not process.alive


def test_worker_driver_failure_never_exports_private_exception(clock, tmp_path, capsys):
    def fail(*args):
        print("synthetic-private")
        raise RuntimeError("synthetic-private")

    path = tmp_path / "worker.json"
    measurement._worker(fail, None, tmp_path, measurement.Deadline(10), path)
    assert json.loads(path.read_text()) == {"status": "failed"}
    assert "synthetic-private" not in repr(capsys.readouterr())
