"""Opt-in source landing migration/privilege checks; all fixture work rolls back."""

import os
from uuid import UUID

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings
from src.warehouse.migrations import apply_migrations, read_migrations, verify_privileges

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_LANDING_INTEGRATION") != "1",
    reason="Landing database checks require explicit opt-in",
)
PROBE_ID = UUID("33333333-0000-4000-8000-000000000002")


def test_landing_migration_and_capability_boundaries() -> None:
    with connect(load_settings()) as connection:
        before = connection.execute("SELECT to_regclass('ops.source_loads')").fetchone()
        with connection.transaction(force_rollback=True):
            migrations = read_migrations()
            apply_migrations(connection, migrations)
            assert apply_migrations(connection, migrations) == []
            verify_privileges(connection)
            connection.execute("SET LOCAL ROLE commercelens_loader")
            connection.execute(
                "INSERT INTO ops.source_loads "
                "(load_id,source_fingerprint,dataset_handle,contract_version,"
                "manifest_sha256,source_files) "
                "VALUES (%s,%s,'olistbr/brazilian-ecommerce/versions/2',1,%s,%s)",
                (PROBE_ID, "b" * 64, "c" * 64, Jsonb({"fixture": True})),
            )
            assert connection.execute(
                "SELECT loaded_by, loaded_at IS NOT NULL FROM ops.source_loads WHERE load_id=%s",
                (PROBE_ID,),
            ).fetchone() == ("postgres", True)
            for name, contract in TABLES.items():
                values = ["00123", "", 'linha 1\r\nlinha 2, "ótimo"', "\\N"]
                row = tuple(values[index % len(values)] for index in range(len(contract.columns)))
                table = sql.Identifier("raw", name)
                with connection.cursor().copy(sql.SQL("COPY {} FROM STDIN").format(table)) as copy:
                    copy.write_row((PROBE_ID, 1, *row))
                fields = sql.SQL(", ").join(map(sql.Identifier, contract.columns))
                assert (
                    connection.execute(
                        sql.SQL("SELECT {} FROM {} WHERE _load_id=%s").format(fields, table),
                        (PROBE_ID,),
                    ).fetchone()
                    == row
                )
                for statement in [
                    sql.SQL("DELETE FROM {} WHERE _load_id=%s").format(table),
                    sql.SQL("UPDATE {} SET _source_row=2 WHERE _load_id=%s").format(table),
                ]:
                    with (
                        pytest.raises(psycopg.errors.InsufficientPrivilege),
                        connection.transaction(),
                    ):
                        connection.execute(statement, (PROBE_ID,))
                with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                    connection.execute(sql.SQL("TRUNCATE {} ").format(table))
                with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                    connection.execute(
                        sql.SQL("INSERT INTO {} SELECT * FROM {} WHERE _load_id=%s").format(
                            table, table
                        ),
                        (PROBE_ID,),
                    )
                for role in ("anon", "authenticated", "service_role"):
                    assert connection.execute(
                        "SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
                        (role, "raw." + name),
                    ).fetchone() == (False,)
            for statement in [
                "UPDATE ops.source_loads SET loaded_by='forbidden'",
                "DELETE FROM ops.source_loads",
                "UPDATE ops.schema_migrations SET checksum='forbidden'",
                "CREATE TABLE raw.__forbidden_landing_probe(id int)",
            ]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                    connection.execute(statement)
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute("INSERT INTO ops.source_loads (loaded_by) VALUES ('forbidden')")
            with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO raw.category_translation VALUES (%s,2,'fixture','fixture')",
                    (UUID(int=0),),
                )
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO raw.category_translation VALUES (%s,0,'fixture','fixture')",
                    (PROBE_ID,),
                )
            with pytest.raises(psycopg.errors.NotNullViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO raw.category_translation VALUES (%s,2,NULL,'fixture')",
                    (PROBE_ID,),
                )
        assert connection.execute("SELECT to_regclass('ops.source_loads')").fetchone() == before
        if before != (None,):
            assert connection.execute(
                "SELECT count(*) FROM ops.source_loads WHERE load_id=%s", (PROBE_ID,)
            ).fetchone() == (0,)
            for name in TABLES:
                assert connection.execute(
                    sql.SQL("SELECT count(*) FROM raw.{} WHERE _load_id=%s").format(
                        sql.Identifier(name)
                    ),
                    (PROBE_ID,),
                ).fetchone() == (0,)
