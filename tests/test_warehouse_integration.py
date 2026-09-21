"""Opt-in real-database recovery tests; run before the first persistent bootstrap.

Requires COMMERCE_WAREHOUSE_INTEGRATION=1 and an empty dedicated development warehouse.
All created roles, schemas, tables, and ledger rows are rolled back. No data is loaded.
"""

import os
from dataclasses import replace

import psycopg
import pytest

from src.warehouse.config import connect, load_settings
from src.warehouse.migrations import (
    Migration,
    MigrationError,
    apply_migrations,
    inspect_database,
    read_migrations,
    verify_privileges,
)

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_INTEGRATION") != "1",
    reason="Real development database checks require explicit opt-in",
)


def test_bootstrap_recovery_history_and_concurrency() -> None:
    settings = load_settings()
    migrations = read_migrations()
    with connect(settings) as first, connect(settings) as second:
        assert inspect_database(first)["schemas"] == {}, "Requires empty warehouse schemas"
        assert first.execute(
            "SELECT count(*) FROM pg_roles WHERE strpos(rolname, 'commercelens_') = 1"
        ).fetchone() == (0,), "Requires no existing CommerceLens capability roles"
        with first.transaction(force_rollback=True):
            assert apply_migrations(first, migrations) == ["0001"]
            verify_privileges(first)
            assert apply_migrations(first, migrations) == []

            with pytest.raises(MigrationError):
                apply_migrations(first, [replace(migrations[0], checksum="0" * 64)])

            failure = Migration(
                "0002",
                "SET LOCAL ROLE commercelens_owner; "
                "CREATE TABLE ops.__commercelens_failure_probe (id integer); SELECT 1 / 0;",
                "a" * 64,
            )
            with pytest.raises(psycopg.errors.DivisionByZero):
                apply_migrations(first, [*migrations, failure])
            assert first.execute(
                "SELECT to_regclass('ops.__commercelens_failure_probe')"
            ).fetchone() == (None,)
            assert first.execute("SELECT count(*) FROM ops.schema_migrations").fetchone() == (1,)

            # A second real session must not race the uncommitted first migration batch.
            second.execute("SET lock_timeout = '250ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                apply_migrations(second, migrations)

        assert inspect_database(first)["schemas"] == {}
        assert first.execute(
            "SELECT count(*) FROM pg_roles WHERE strpos(rolname, 'commercelens_') = 1"
        ).fetchone() == (0,)

        # Reconstruct from the same source in a fresh session after complete rollback.
        # This validates bootstrap reconstruction, not a data backup/restore.
        with second.transaction(force_rollback=True):
            assert apply_migrations(second, migrations) == ["0001"]
            verify_privileges(second)
            assert apply_migrations(second, migrations) == []
        assert inspect_database(second)["schemas"] == {}
        assert second.execute(
            "SELECT count(*) FROM pg_roles WHERE strpos(rolname, 'commercelens_') = 1"
        ).fetchone() == (0,)
