"""Offline grant transaction boundaries; native ACL semantics have a separate gate."""

from contextlib import contextmanager
from pathlib import Path

import pytest

from src.analytics.access import MARTS, grant_analytics_reader
from src.warehouse.config import ROOT


class Connection:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.active = False
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def transaction(self):
        self.active = True
        try:
            yield
            if self.failure == "commit":
                raise RuntimeError("synthetic private detail")
        except BaseException:
            self.rolled_back = True
            raise
        else:
            self.committed = True
        finally:
            self.active = False

    def execute(self, statement, *, prepare):
        assert self.active and prepare is False
        self.calls.append(statement)
        if self.failure == len(self.calls):
            raise RuntimeError("synthetic private detail")


def test_grants_are_exact_and_share_one_transaction():
    connection = Connection()
    grant_analytics_reader(connection)
    assert connection.committed and not connection.rolled_back
    assert len(connection.calls) == 3
    grants = [
        line
        for script in connection.calls
        for line in script.splitlines()
        if line.startswith("GRANT ")
    ]
    assert grants == [
        "GRANT SELECT ON TABLE marts.mart_order_components TO commercelens_reader;",
        "GRANT SELECT ON TABLE marts.mart_order_kpis TO commercelens_reader;",
        "GRANT SELECT ON TABLE marts.mart_item_kpis TO commercelens_reader;",
    ]
    for name, script in zip(MARTS, connection.calls, strict=True):
        assert "session_user <> 'commercelens_transform'" in script
        assert "NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper" in script
        assert "security_invoker" in script and "pg_auth_members" in script
        assert "SELECT WITH GRANT OPTION" in script
        assert "('anon','authenticated','service_role')" in script
        assert "has_schema_privilege('public','marts','USAGE,CREATE')" in script
        assert f"c.relname='{name}'" in script
        assert "c.oid not in ('marts.mart_order_components'::regclass," in script
        assert "'marts.mart_order_kpis'::regclass,'marts.mart_item_kpis'::regclass)" in script


@pytest.mark.parametrize("failure", [1, 2, 3, "commit"])
def test_later_guard_or_commit_failure_rolls_back_entire_batch(failure, capsys):
    connection = Connection(failure)
    with pytest.raises(RuntimeError):
        grant_analytics_reader(connection)
    assert connection.rolled_back and not connection.committed and not connection.active
    assert len(connection.calls) == (failure if isinstance(failure, int) else 3)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("copies", [0, 2])
def test_changed_exclusion_contract_fails_before_sql(tmp_path, copies):
    original = (ROOT / "warehouse/access/mart_order_components.sql").read_text("utf-8")
    exclusion = "c.oid <> 'marts.mart_order_components'::regclass"
    changed = original.replace(exclusion, "\n".join([exclusion] * copies))
    folder = tmp_path / "warehouse/access"
    folder.mkdir(parents=True)
    (folder / "mart_order_components.sql").write_text(changed, encoding="utf-8")
    connection = Connection()
    with pytest.raises(ValueError, match="guard changed"):
        grant_analytics_reader(connection, root=tmp_path)
    assert not connection.active and not connection.calls


def test_missing_guard_fails_before_sql(tmp_path: Path):
    connection = Connection()
    with pytest.raises(FileNotFoundError):
        grant_analytics_reader(connection, root=tmp_path)
    assert not connection.active and not connection.calls


@pytest.mark.parametrize("row", [None, (False,), (None,), (True,)])
def test_catalog_contract_requires_explicit_true(row):
    from src.analytics.access import verify_reader_catalog

    class CatalogConnection:
        def execute(self, statement, parameters):
            assert parameters == (["marts." + name for name in MARTS],) * 3
            return self

        def fetchone(self):
            return row

    if row == (True,):
        verify_reader_catalog(CatalogConnection())
    else:
        with pytest.raises(ValueError, match="capability contract"):
            verify_reader_catalog(CatalogConnection())


@pytest.mark.parametrize("failure", ["catalog", "probe", "close", None])
def test_native_grant_verification_and_failure_receipt(tmp_path, monkeypatch, capsys, failure):
    import json

    from scripts import phase5_native as native

    class ManagedConnection(Connection):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            if failure == "close":
                raise RuntimeError("synthetic private close detail")

    connection = ManagedConnection()
    monkeypatch.setattr(native, "ROOT", tmp_path)
    monkeypatch.setattr(native, "_isolated_root", lambda *args: tmp_path)
    monkeypatch.setattr(native, "_settings", lambda *args: object())
    monkeypatch.setattr(native, "metadata", lambda *args: {"relations": [], "raw_bytes": 1})
    monkeypatch.setattr(native, "connect", lambda *args: connection)
    monkeypatch.setattr(
        native, "grant_analytics_reader", lambda c: c.execute("grant", prepare=False)
    )

    def catalog(c):
        assert c.active
        if failure == "catalog":
            raise ValueError("synthetic private catalog detail")

    def probes(settings):
        assert connection.committed
        if failure == "probe":
            raise ValueError("synthetic private probe detail")
        return {"verified": True}

    monkeypatch.setattr(native, "verify_reader_catalog", catalog)
    monkeypatch.setattr(native, "verify_access", probes)
    monkeypatch.setattr(
        "sys.argv",
        ["native", "grant", "--settings-root", str(tmp_path), "--expected-project-ref", "a" * 20],
    )
    assert native.main() == (1 if failure else 0)
    captured = capsys.readouterr()
    assert "synthetic private" not in captured.out + captured.err
    if failure:
        receipt = json.loads(
            next((tmp_path / ".artifacts/phase-5").glob("*/failure.json")).read_text()
        )
        assert receipt["grant_attempted"] is True
        assert receipt["grant_committed"] is (failure != "catalog")
        assert receipt["recovery"] == "Inspect grants before retry"
        assert connection.rolled_back is (failure == "catalog")
    else:
        assert connection.committed
