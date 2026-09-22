"""Offline reconciliation failures that row counts or money totals alone cannot find."""

from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path

import pytest
from test_warehouse_source import snapshot as snapshot
from test_warehouse_source import write_table

from src.ingestion.olist import AcquisitionError
from src.warehouse import loading, source


class SnapshotCursor:
    def __init__(self, rows: list[tuple]):
        self.rows = rows
        self.itersize = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, parameters):
        pass

    def __iter__(self):
        return iter(self.rows)


class SnapshotConnection:
    def __init__(self, root: Path, plan: source.SourcePlan):
        self.rows = {
            name: [
                (index, *row) for index, row in enumerate(source.iter_source_rows(root, name), 1)
            ]
            for name in plan.tables
        }
        self.money = {
            name: tuple(Decimal(value) for value in table.money.values())
            for name, table in plan.tables.items()
            if table.money
        }
        self.result = None

    def cursor(self, *, name: str):
        return SnapshotCursor(self.rows[name.removeprefix("verify_")])

    def execute(self, query, parameters):
        statement = query.as_string()
        name = next(name for name in self.money if f'raw."{name}"' in statement)
        self.result = self.money[name]
        return self

    def fetchone(self):
        return self.result


def test_verification_rejects_changed_text_despite_same_counts_and_money(snapshot: Path) -> None:
    plan = source.prepare_source(snapshot)
    connection = SnapshotConnection(snapshot, plan)
    loading.verify_snapshot(connection, plan)
    before_money = connection.money.copy()
    original = connection.rows["customers"][0]
    connection.rows["customers"][0] = (*original[:-1], "different private text")
    with pytest.raises(loading.LoadError, match="content or row count") as error:
        loading.verify_snapshot(connection, plan)
    assert connection.money == before_money
    assert len(connection.rows["customers"]) == plan.tables["customers"].rows
    assert "different private text" not in str(error.value)


@pytest.mark.parametrize("kind", ["missing", "extra", "ordinal_gap", "null"])
def test_verification_rejects_incomplete_or_malformed_stored_rows(
    snapshot: Path, kind: str
) -> None:
    plan = source.prepare_source(snapshot)
    connection = SnapshotConnection(snapshot, plan)
    row = connection.rows["customers"][0]
    if kind == "missing":
        connection.rows["customers"] = []
    elif kind == "extra":
        connection.rows["customers"].append((2, *row[1:]))
    elif kind == "ordinal_gap":
        connection.rows["customers"][0] = (2, *row[1:])
    else:
        connection.rows["customers"][0] = (*row[:-1], None)
    with pytest.raises(loading.LoadError):
        loading.verify_snapshot(connection, plan)


def test_exact_money_is_independently_reconciled(snapshot: Path) -> None:
    plan = source.prepare_source(snapshot)
    connection = SnapshotConnection(snapshot, plan)
    connection.money["order_items"] = (Decimal("0.11"), Decimal("0.10"))
    with pytest.raises(loading.LoadError, match="monetary reconciliation"):
        loading.verify_snapshot(connection, plan)


@pytest.mark.parametrize("kind", ["source", "manifest_bytes"])
def test_stale_plan_is_rejected_before_database_access(snapshot: Path, kind: str) -> None:
    plan = source.prepare_source(snapshot)
    if kind == "source":
        write_table(snapshot, "category_translation", [["changed", "source"]])
    else:
        manifest = snapshot / "data/source-manifest.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    # An object with no database interface proves rejection occurs before any SQL.
    with pytest.raises((loading.LoadError, AcquisitionError)):
        loading.load_source(object(), snapshot, plan)


def test_empty_but_allocated_database_requires_capacity_recovery(snapshot: Path) -> None:
    """Rolled-back COPY can leave physical space even when no registry rows remain."""

    class AllocatedConnection:
        def transaction(self):
            return nullcontext()

        def execute(self, query, parameters=None):
            self.query = query
            assert not query.startswith(("INSERT", "COPY"))
            return self

        def fetchall(self):
            return []

        def fetchone(self):
            if "session_user" in self.query:
                return ("commercelens_ingest", "postgres")
            return (100_000_000,)

    with pytest.raises(loading.LoadError, match="landing budget"):
        loading.load_source(AllocatedConnection(), snapshot)
