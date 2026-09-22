"""Atomic, immutable Olist landing with byte provenance and logical-content verification."""

import hashlib
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from src.ingestion.olist import DATASET_HANDLE, sha256_file, verify_raw
from src.validation.contracts import TABLES
from src.warehouse.migrations import LOCK_ID
from src.warehouse.source import (
    LANDING_CONTRACT_VERSION,
    SourcePlan,
    iter_source_rows,
    prepare_source,
    update_digest,
)

RAW_STORAGE_CEILING = 367_000_000
DATABASE_STORAGE_CEILING = 400_000_000


class LoadError(ValueError):
    """The source, stored snapshot, or capacity gate is unsafe to publish."""


def file_evidence(plan: SourcePlan) -> dict[str, object]:
    if set(plan.tables) != set(TABLES) or plan.manifest["dataset_handle"] != DATASET_HANDLE:
        raise LoadError("The load plan must cover the complete approved source contract")
    return {
        name: {
            **asdict(evidence),
            "filename": TABLES[name].filename,
            **plan.manifest["files"][TABLES[name].filename],
        }
        for name, evidence in plan.tables.items()
    }


def verify_snapshot(
    connection: psycopg.Connection,
    plan: SourcePlan,
    progress: Callable[[str], None] | None = None,
) -> None:
    """Re-read every field in logical source order; counts and sums alone miss corruption."""
    for name, contract in TABLES.items():
        fields = sql.SQL(", ").join(map(sql.Identifier, ["_source_row", *contract.columns]))
        query = sql.SQL("SELECT {} FROM raw.{} WHERE _load_id = %s ORDER BY _source_row").format(
            fields, sql.Identifier(name)
        )
        digest = hashlib.sha256()
        count = 0
        with connection.cursor(name="verify_" + name) as cursor:
            cursor.itersize = 20_000
            cursor.execute(query, (plan.load_id,))
            for count, row in enumerate(cursor, 1):
                if row[0] != count or any(not isinstance(value, str) for value in row[1:]):
                    raise LoadError("Stored source shape or logical ordinal differs")
                update_digest(digest, count, tuple(row[1:]))
        expected = plan.tables[name]
        if count != expected.rows or digest.hexdigest() != expected.content_sha256:
            raise LoadError("Stored source content or row count differs from verified input")
        if expected.money:
            sums = sql.SQL(", ").join(
                sql.SQL("sum({}::numeric)").format(sql.Identifier(column))
                for column in expected.money
            )
            values = connection.execute(
                sql.SQL("SELECT {} FROM raw.{} WHERE _load_id = %s").format(
                    sums, sql.Identifier(name)
                ),
                (plan.load_id,),
            ).fetchone()
            if values is None or list(values) != [
                Decimal(value) for value in expected.money.values()
            ]:
                raise LoadError("Exact monetary reconciliation failed")
        if progress:
            progress(f"Verified {name}")


def _verify_source(root: Path, plan: SourcePlan) -> None:
    if (
        verify_raw(root) != plan.manifest
        or sha256_file(root / "data/source-manifest.json") != plan.manifest_sha256
    ):
        raise LoadError("Source provenance changed; snapshot not committed")


def _storage_usage(connection: psycopg.Connection) -> dict[str, int]:
    raw_size = connection.execute(
        "SELECT coalesce(sum(pg_total_relation_size(c.oid)),0) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='raw' AND c.relkind='r'"
    ).fetchone()
    database_size = connection.execute("SELECT pg_database_size(current_database())").fetchone()
    if raw_size is None or raw_size[0] > RAW_STORAGE_CEILING:
        raise LoadError("Actual raw storage exceeds the approved budget")
    if database_size is None or database_size[0] > DATABASE_STORAGE_CEILING:
        raise LoadError("Actual database storage leaves insufficient build headroom")
    return {"raw_bytes": int(raw_size[0]), "database_bytes": database_size[0]}


def load_source(
    connection: psycopg.Connection,
    root: Path,
    plan: SourcePlan | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """One snapshot per capacity-reviewed target; changed content needs a fresh storage review."""
    plan = prepare_source(root) if plan is None else plan
    evidence = file_evidence(plan)
    # The CLI prepares before connecting. Recheck a supplied plan before touching
    # the database as well, then again after COPY/verification and before commit.
    _verify_source(root, plan)
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        identity = connection.execute("SELECT session_user, current_database()").fetchone()
        if identity != ("commercelens_ingest", "postgres"):
            raise LoadError("Use the dedicated restricted ingestion login")
        connection.execute("SET LOCAL ROLE commercelens_loader")
        connection.execute("SET LOCAL statement_timeout = '10min'")
        connection.execute("SET LOCAL idle_in_transaction_session_timeout = '120s'")
        existing = connection.execute(
            "SELECT load_id, source_fingerprint, dataset_handle, contract_version, source_files "
            "FROM ops.source_loads"
        ).fetchall()
        if existing:
            identity = (
                plan.load_id,
                plan.fingerprint,
                DATASET_HANDLE,
                LANDING_CONTRACT_VERSION,
                evidence,
            )
            if len(existing) != 1 or existing[0] != identity:
                raise LoadError("A different snapshot requires a new capacity and retention review")
            verify_snapshot(connection, plan, progress)
            _verify_source(root, plan)
            return {
                "status": "verified_existing",
                "load_id": str(plan.load_id),
                "rows": sum(table.rows for table in plan.tables.values()),
                **_storage_usage(connection),
            }

        current_size = connection.execute("SELECT pg_database_size(current_database())").fetchone()
        if current_size is None or current_size[0] + RAW_STORAGE_CEILING > DATABASE_STORAGE_CEILING:
            raise LoadError("Database no longer fits the approved source landing budget")
        connection.execute(
            "INSERT INTO ops.source_loads "
            "(load_id, source_fingerprint, dataset_handle, contract_version, "
            "manifest_sha256, source_files) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                plan.load_id,
                plan.fingerprint,
                DATASET_HANDLE,
                LANDING_CONTRACT_VERSION,
                plan.manifest_sha256,
                Jsonb(evidence),
            ),
        )
        for name, contract in TABLES.items():
            fields = sql.SQL(", ").join(
                map(sql.Identifier, ["_load_id", "_source_row", *contract.columns])
            )
            statement = sql.SQL("COPY raw.{} ({}) FROM STDIN").format(sql.Identifier(name), fields)
            with connection.cursor() as cursor, cursor.copy(statement) as copy:
                for ordinal, row in enumerate(iter_source_rows(root, name), 1):
                    copy.write_row((plan.load_id, ordinal, *row))
            if progress:
                progress(f"Copied {name}")
        verify_snapshot(connection, plan, progress)
        _verify_source(root, plan)
        return {
            "status": "loaded",
            "load_id": str(plan.load_id),
            "rows": sum(table.rows for table in plan.tables.values()),
            **_storage_usage(connection),
        }
