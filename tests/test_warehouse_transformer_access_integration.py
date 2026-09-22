"""Check the actual transformer login with tiny views and unconditional rollback."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from src.warehouse.config import connect, load_settings
from src.warehouse.migrations import LOCK_ID

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_TRANSFORMER_ACCESS_INTEGRATION") != "1",
    reason="Restricted transformer login checks require explicit opt-in",
)


def test_actual_transformer_identity_views_and_permission_boundaries() -> None:
    name = "__transformer_access_" + uuid4().hex
    schemas = ("staging", "core", "marts")
    with connect(load_settings(purpose="transformer")) as connection:
        # Force rollback even when a denial unexpectedly succeeds or an assertion
        # is changed later. No probe view or accidental privilege change can commit.
        with connection.transaction(force_rollback=True):
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
            assert connection.execute(
                "SELECT session_user, current_user, current_database(), "
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
            ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
            assert connection.execute(
                "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
                "rolreplication, rolbypassrls, rolconnlimit "
                "FROM pg_roles WHERE rolname=session_user"
            ).fetchone() == (True, False, False, False, False, False, False, 2)
            assert connection.execute(
                "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
                "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
                "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user"
            ).fetchall() == [("commercelens_transformer", False, False, True)]
            with (
                pytest.raises(psycopg.errors.InsufficientPrivilege),
                connection.transaction(force_rollback=True),
            ):
                connection.execute("SELECT 1 FROM raw.customers LIMIT 0")

            connection.execute("SET LOCAL ROLE commercelens_transformer")
            assert connection.execute("SELECT current_user").fetchone() == (
                "commercelens_transformer",
            )
            # This queries no source values and allocates no materialized data.
            assert connection.execute("SELECT 1 FROM raw.customers LIMIT 0").fetchall() == []
            assert connection.execute(
                "SELECT count(*), bool_and(has_table_privilege(current_user, c.oid, 'SELECT') "
                "AND NOT has_table_privilege(current_user, c.oid, "
                "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='raw' AND c.relkind='r'"
            ).fetchone() == (9, True)

            for schema in schemas:
                connection.execute(
                    sql.SQL(
                        "CREATE VIEW {}.{} AS SELECT 1 AS probe FROM raw.customers LIMIT 0"
                    ).format(sql.Identifier(schema), sql.Identifier(name))
                )
                assert connection.execute(
                    "SELECT r.rolname, c.relkind FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN pg_roles r ON r.oid=c.relowner "
                    "WHERE n.nspname=%s AND c.relname=%s",
                    (schema, name),
                ).fetchone() == ("commercelens_transformer", "v")
                assert (
                    connection.execute(
                        sql.SQL("SELECT * FROM {}.{}").format(
                            sql.Identifier(schema), sql.Identifier(name)
                        )
                    ).fetchall()
                    == []
                )
                # Check effective privileges, including PUBLIC and inherited
                # membership, on the actual uncommitted view for all API roles.
                assert connection.execute(
                    "SELECT count(*), bool_and("
                    "NOT has_schema_privilege(r.oid, n.oid, 'USAGE,CREATE') "
                    "AND NOT has_table_privilege(r.oid, c.oid, "
                    "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
                    "FROM pg_roles r CROSS JOIN pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE r.rolname IN ('anon','authenticated','service_role') "
                    "AND n.nspname=%s AND c.relname=%s",
                    (schema, name),
                ).fetchone() == (3, True)

            for statement in (
                "SET LOCAL ROLE postgres",
                "SET LOCAL ROLE commercelens_owner",
                "SET LOCAL ROLE commercelens_loader",
                "SET LOCAL ROLE commercelens_ingest",
                "SET LOCAL ROLE commercelens_reader",
                "SELECT count(*) FROM ops.schema_migrations",
                "INSERT INTO raw.customers SELECT * FROM raw.customers WHERE false",
                "UPDATE raw.customers SET customer_city='' WHERE false",
                "DELETE FROM raw.customers WHERE false",
                sql.SQL("CREATE VIEW raw.{} AS SELECT 1 AS probe").format(sql.Identifier(name)),
                sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)),
            ):
                with (
                    pytest.raises(psycopg.errors.InsufficientPrivilege),
                    connection.transaction(force_rollback=True),
                ):
                    connection.execute(statement)

        assert connection.execute("SELECT current_user").fetchone() == ("commercelens_transform",)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN ('staging', 'core', 'marts', 'raw') AND c.relname=%s",
            (name,),
        ).fetchone() == (0,)
        assert (
            connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone()
            is None
        )
