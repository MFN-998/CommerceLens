"""Opt-in real-login COPY/recovery checks; require an empty landing and roll back all fixtures."""

import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from test_warehouse_source import snapshot as snapshot
from test_warehouse_source import write_manifest, write_table

from src.ingestion.olist import AcquisitionError
from src.validation.contracts import TABLES
from src.warehouse import loading, source
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_LOADING_INTEGRATION") != "1",
    reason="Restricted-loader database checks require explicit opt-in and an empty landing",
)


def assert_empty(connection: psycopg.Connection) -> None:
    assert connection.execute("SELECT count(*) FROM ops.source_loads").fetchone() == (0,)
    for name in TABLES:
        assert connection.execute(
            sql.SQL("SELECT count(*) FROM raw.{}").format(sql.Identifier(name))
        ).fetchone() == (0,)


@pytest.fixture
def connection() -> Iterator[psycopg.Connection]:
    with connect(load_settings(purpose="loader")) as connection:
        with connection.transaction(force_rollback=True):
            connection.execute("SET LOCAL ROLE commercelens_loader")
            assert connection.execute("SELECT count(*) FROM ops.source_loads").fetchone() == (0,), (
                "Run destructive-fixture checks only on an empty reviewed development landing"
            )
            yield connection
        with connection.transaction(force_rollback=True):
            connection.execute("SET LOCAL ROLE commercelens_loader")
            assert_empty(connection)


@pytest.fixture
def rich_snapshot(snapshot: Path) -> Path:
    write_table(snapshot, "customers", [["id", "identity", "00123", "são paulo", "SP"]])
    review = ["review", "order", "5", "", 'Bom, "ótimo"!\r\nSegunda linha', "", "\\N"]
    write_table(snapshot, "order_reviews", [review, review])
    geo = ["00123", "-1.00", "-2.00", "city", "SP"]
    write_table(snapshot, "geolocation", [geo, geo])
    write_table(
        snapshot,
        "order_items",
        [
            ["order", "1", "product", "seller", "date", "0.10", "1.02"],
            ["order", "2", "product", "seller", "date", "0.20", "0.01"],
        ],
    )
    write_manifest(snapshot)
    return snapshot


def test_complete_copy_retry_and_original_attribution(
    connection: psycopg.Connection, rich_snapshot: Path
) -> None:
    plan = source.prepare_source(rich_snapshot)
    first = loading.load_source(connection, rich_snapshot, plan)
    assert first["status"] == "loaded"
    assert first["rows"] == sum(table.rows for table in plan.tables.values())
    assert 0 < first["raw_bytes"] <= loading.RAW_STORAGE_CEILING
    assert 0 < first["database_bytes"] <= loading.DATABASE_STORAGE_CEILING
    assert connection.execute(
        "SELECT customer_zip_code_prefix, customer_city FROM raw.customers"
    ).fetchone() == ("00123", "são paulo")
    assert connection.execute(
        "SELECT review_comment_title, review_comment_message, review_answer_timestamp "
        "FROM raw.order_reviews ORDER BY _source_row LIMIT 1"
    ).fetchone() == ("", 'Bom, "ótimo"!\r\nSegunda linha', "\\N")
    assert connection.execute("SELECT count(*) FROM raw.geolocation").fetchone() == (2,)
    assert connection.execute(
        "SELECT sum(price::numeric), sum(freight_value::numeric) FROM raw.order_items"
    ).fetchone() == (Decimal("0.30"), Decimal("1.03"))
    registry = connection.execute(
        "SELECT load_id, manifest_sha256, source_files, loaded_by, loaded_at FROM ops.source_loads"
    ).fetchone()
    assert registry is not None and registry[3] == "commercelens_ingest"
    assert registry[1] == plan.manifest_sha256
    assert registry[2] == loading.file_evidence(plan)
    second = loading.load_source(connection, rich_snapshot)
    assert second["status"] == "verified_existing"
    assert second["load_id"] == first["load_id"]
    # A fresh acquisition timestamp cannot duplicate identical source content or
    # overwrite the provenance/timestamp of the original committed snapshot.
    write_manifest(rich_snapshot, "2026-09-03T00:00:00+00:00")
    assert loading.load_source(connection, rich_snapshot)["status"] == "verified_existing"
    assert (
        connection.execute(
            "SELECT load_id, manifest_sha256, source_files, loaded_by, loaded_at "
            "FROM ops.source_loads"
        ).fetchone()
        == registry
    )


@pytest.mark.parametrize(
    "failure", ["interrupted", "copy_text_changed", "source_changed_after_copy", "manifest_bytes"]
)
def test_interrupted_or_changed_input_rolls_back_every_table_and_registry(
    connection: psycopg.Connection, rich_snapshot: Path, failure: str
) -> None:
    plan = source.prepare_source(rich_snapshot)

    def fail_after_customers(name: str) -> None:
        if name != "Copied customers":
            return
        if failure == "interrupted":
            raise RuntimeError("Simulated interruption after the first COPY")
        if failure == "copy_text_changed":
            # Same number of rows and unchanged money; only nonmonetary text
            # changes before its COPY, so full content reconciliation must fail.
            write_table(rich_snapshot, "category_translation", [["changed", "text"]])
        elif failure == "source_changed_after_copy":
            write_table(rich_snapshot, "customers", [["id", "identity", "99999", "city", "SP"]])
        else:
            path = rich_snapshot / "data/source-manifest.json"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises((RuntimeError, loading.LoadError, AcquisitionError)):
        loading.load_source(connection, rich_snapshot, plan, fail_after_customers)
    assert_empty(connection)


@pytest.mark.parametrize("gate", ["preflight", "raw", "database"])
def test_capacity_gate_prevents_or_rolls_back_the_entire_load(
    connection: psycopg.Connection,
    rich_snapshot: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate: str,
) -> None:
    if gate == "preflight":
        monkeypatch.setattr(loading, "DATABASE_STORAGE_CEILING", 1)

    def tighten_after_copy(name: str) -> None:
        if name == f"Copied {tuple(TABLES)[-1]}" and gate != "preflight":
            setting = "RAW_STORAGE_CEILING" if gate == "raw" else "DATABASE_STORAGE_CEILING"
            monkeypatch.setattr(loading, setting, 1)

    with pytest.raises(loading.LoadError, match="budget|headroom"):
        loading.load_source(connection, rich_snapshot, progress=tighten_after_copy)
    assert_empty(connection)


def test_changed_snapshot_is_refused_without_touching_the_existing_one(
    connection: psycopg.Connection, rich_snapshot: Path
) -> None:
    original = source.prepare_source(rich_snapshot)
    loading.load_source(connection, rich_snapshot, original)
    write_table(rich_snapshot, "category_translation", [["new", "snapshot"]])
    write_manifest(rich_snapshot)
    with pytest.raises(loading.LoadError, match="capacity and retention review"):
        loading.load_source(connection, rich_snapshot)
    assert connection.execute("SELECT load_id FROM ops.source_loads").fetchall() == [
        (original.load_id,)
    ]
    loading.verify_snapshot(connection, original)


def test_admin_connection_is_not_an_ingestion_fallback(rich_snapshot: Path) -> None:
    with connect(load_settings()) as connection, connection.transaction(force_rollback=True):
        # Keep the fixture safe even if the identity safeguard itself regresses.
        assert_empty(connection)
        with pytest.raises(loading.LoadError, match="restricted ingestion login"):
            loading.load_source(connection, rich_snapshot)
