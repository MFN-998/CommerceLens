"""Loading never uses administration settings or reports uncertain commits as successful."""

from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest

from src.warehouse import __main__ as cli


@pytest.mark.parametrize("close_failure", [False, True])
def test_load_cli_uses_loader_and_reports_only_after_clean_exit(monkeypatch, capsys, close_failure):
    events = []
    secret = "synthetic-private-driver-detail"

    def settings(*, purpose):
        assert purpose == "loader"
        return SimpleNamespace(project_ref="abcdefghijklmnopqrst")

    def prepare(root):
        events.append("prepare")
        return object()

    @contextmanager
    def connection(settings):
        assert events == ["prepare"]
        events.append("connect")
        yield object()
        if close_failure:
            raise psycopg.OperationalError(secret)
        events.append("closed")

    def load(connection, root, plan, progress):
        progress("Copied customers")
        return {"status": "loaded"}

    monkeypatch.setattr(cli, "load_settings", settings)
    monkeypatch.setattr(cli, "prepare_source", prepare)
    monkeypatch.setattr(cli, "connect", connection)
    monkeypatch.setattr(cli, "load_source", load)
    monkeypatch.setattr("sys.argv", ["warehouse", "load"])
    assert cli.main() == (1 if close_failure else 0)
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    if close_failure:
        assert captured.out == ""
    else:
        assert events[-1] == "closed"
        assert '"status": "loaded"' in captured.out


@pytest.mark.parametrize("command", ["parse", "debug"])
def test_dbt_cli_never_loads_administrator_configuration(monkeypatch, capsys, command):
    def refuse_admin():
        pytest.fail("dbt commands must never request administrator settings")

    def run_dbt(actual_command):
        assert actual_command == command
        return {"command": f"dbt-{command}", "status": "passed"}

    monkeypatch.setattr(cli, "load_settings", refuse_admin)
    monkeypatch.setattr(cli, "run_dbt", run_dbt)
    monkeypatch.setattr("sys.argv", ["warehouse", f"dbt-{command}"])
    assert cli.main() == 0
    assert '"status": "passed"' in capsys.readouterr().out
