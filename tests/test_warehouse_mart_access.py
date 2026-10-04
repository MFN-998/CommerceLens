"""Offline control-flow checks for the fixed post-model reader grant.

Import adopted production modules and read the reviewed grant file unchanged.
Fakes prove transaction/output/configuration boundaries, not PostgreSQL ACL or
idempotent privilege semantics; native read-only access verification owns those.
No private configuration, live connection, fixture files or SQL parsing are used.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from src.warehouse import __main__ as cli
from src.warehouse import access

SECRET = "synthetic-private-driver-detail"
EXPECTED_RESULT = {
    "status": "granted",
    "model": "marts.mart_order_components",
    "capability": "SELECT",
}


class GrantConnection:
    """Record driver boundaries without interpreting or granting SQL privileges."""

    def __init__(
        self, events: list[str], failure: str | None = None, error=psycopg.OperationalError
    ):
        self.events = events
        self.failure = failure
        self.error = error
        self.active = False
        self.calls: list[tuple[str, bool]] = []

    @contextmanager
    def transaction(self):
        self.events.append("transaction_enter")
        if self.failure == "transaction":
            raise self.error(SECRET)
        self.active = True
        try:
            yield
            if self.failure == "commit":
                raise self.error(SECRET)
        except BaseException:
            self.events.append("transaction_failed")
            raise
        else:
            self.events.append("transaction_committed")
        finally:
            self.active = False

    def execute(self, script: str, *, prepare: bool) -> None:
        assert self.active, "The grant script must execute inside its transaction"
        self.events.append("execute")
        self.calls.append((script, prepare))
        if self.failure == "execute":
            raise self.error(SECRET)


@pytest.fixture(autouse=True)
def forbid_unstubbed_external_or_administrative_operations(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Grant command reached an unstubbed connection/configuration or unrelated path")

    for name in (
        "load_settings",
        "connect",
        "read_migrations",
        "apply_migrations",
        "inspect_database",
        "verify_privileges",
        "provision_loader",
        "provision_transformer",
        "prepare_source",
        "load_source",
        "run_dbt",
    ):
        monkeypatch.setattr(cli, name, unexpected)


def configure_cli(monkeypatch, capsys, *, failure=None, error=psycopg.OperationalError):
    events: list[str] = []
    settings = SimpleNamespace(purpose="transformer")
    connection = GrantConnection(events, failure, error)

    def load_settings(*, purpose):
        assert purpose == "transformer"
        events.append("settings")
        return settings

    @contextmanager
    def connect(actual_settings):
        assert actual_settings is settings
        events.append("connect")
        if failure == "connect":
            raise error(SECRET)
        events.append("connected")
        try:
            yield connection
        finally:
            events.append("closing")
            captured = capsys.readouterr()
            assert captured.out == captured.err == "", "Output preceded clean connection exit"
            if failure == "close":
                raise error(SECRET)
            events.append("closed")

    monkeypatch.setattr(cli, "load_settings", load_settings)
    monkeypatch.setattr(cli, "connect", connect)
    monkeypatch.setattr("sys.argv", ["warehouse", "grant-mart-reader"])
    return connection, events


def test_reviewed_script_executes_atomically_and_repeat_uses_unchanged_script_and_result() -> None:
    events: list[str] = []
    connection = GrantConnection(events)
    script = (access.ROOT / "warehouse/access/mart_order_components.sql").read_text("utf-8")
    first = access.grant_mart_reader(connection)
    second = access.grant_mart_reader(connection)
    assert first == second == EXPECTED_RESULT
    assert connection.calls == [(script, False), (script, False)]
    assert events == ["transaction_enter", "execute", "transaction_committed"] * 2
    assert not connection.active


def test_missing_script_raises_before_any_transaction_or_sql_call(monkeypatch, capsys) -> None:
    events: list[str] = []
    connection = GrantConnection(events)
    root = Path("synthetic-project")

    def missing(path, encoding):
        assert path == root / "warehouse/access/mart_order_components.sql"
        assert encoding == "utf-8"
        raise FileNotFoundError(SECRET)

    monkeypatch.setattr(Path, "read_text", missing)
    with pytest.raises(FileNotFoundError, match=SECRET):
        access.grant_mart_reader(connection, root=root)
    assert events == connection.calls == []
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_cli_uses_only_transformer_configuration_and_reports_after_commit_and_close(
    monkeypatch, capsys
) -> None:
    connection, events = configure_cli(monkeypatch, capsys)
    assert cli.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"command": "grant-mart-reader", **EXPECTED_RESULT}
    assert captured.err == ""
    assert events == [
        "settings",
        "connect",
        "connected",
        "transaction_enter",
        "execute",
        "transaction_committed",
        "closing",
        "closed",
    ]
    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    "failure,error,status",
    [
        ("connect", psycopg.OperationalError, 1),
        ("transaction", psycopg.OperationalError, 1),
        ("execute", psycopg.errors.InsufficientPrivilege, 1),
        ("commit", psycopg.OperationalError, 1),
        ("close", psycopg.OperationalError, 1),
        ("execute", KeyboardInterrupt, 130),
    ],
)
def test_connection_transaction_execution_commit_close_or_interrupt_failure_is_secret_safe(
    monkeypatch, capsys, failure, error, status
) -> None:
    connection, events = configure_cli(monkeypatch, capsys, failure=failure, error=error)
    assert cli.main() == status
    captured = capsys.readouterr()
    assert captured.out == ""
    assert SECRET not in captured.out + captured.err
    assert captured.err
    assert not connection.active
    if failure in ("connect", "transaction"):
        assert connection.calls == []
    elif failure == "close":
        assert "transaction_committed" in events
        assert "closed" not in events
    else:
        assert "transaction_committed" not in events
        assert events[-1] == "closed"


def test_cli_missing_script_closes_connection_without_sql_success_or_path_detail(
    monkeypatch, capsys
) -> None:
    connection, events = configure_cli(monkeypatch, capsys)

    def missing(path, encoding):
        assert path == access.ROOT / "warehouse/access/mart_order_components.sql"
        assert encoding == "utf-8"
        raise FileNotFoundError(SECRET)

    monkeypatch.setattr(Path, "read_text", missing)
    assert cli.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert SECRET not in captured.err
    assert captured.err
    assert connection.calls == []
    assert events == ["settings", "connect", "connected", "closing", "closed"]


@pytest.mark.parametrize("error", [ValueError, OSError])
def test_transformer_configuration_failure_has_no_fallback_or_connection(
    monkeypatch, capsys, error
) -> None:
    purposes = []

    def invalid(*, purpose):
        purposes.append(purpose)
        raise error(SECRET)

    monkeypatch.setattr(cli, "load_settings", invalid)
    monkeypatch.setattr("sys.argv", ["warehouse", "grant-mart-reader"])
    assert cli.main() == 1
    captured = capsys.readouterr()
    assert purposes == ["transformer"]
    assert captured.out == ""
    assert SECRET not in captured.err
    assert captured.err


def test_grant_cli_rejects_model_selection_before_configuration_or_database_access(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["warehouse", "grant-mart-reader", "--select", "mart_order_components"]
    )
    assert cli.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err
