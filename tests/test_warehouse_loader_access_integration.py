"""Exercise the actual restricted login, without source writes or admin impersonation."""

import os

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_LOADER_ACCESS_INTEGRATION") != "1",
    reason="Restricted login checks require explicit opt-in",
)


def test_actual_loader_identity_and_permission_boundaries() -> None:
    with connect(load_settings(purpose="loader")) as connection:
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("commercelens_ingest", "commercelens_ingest", "postgres", True)
        assert connection.execute(
            "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
            "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=session_user"
        ).fetchone() == (True, False, False, False, False, False, False, 2)
        assert connection.execute(
            "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
            "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
            "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user"
        ).fetchall() == [("commercelens_loader", False, False, True)]
        with connection.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute("SELECT count(*) FROM raw.customers")
            connection.execute("SET LOCAL ROLE commercelens_loader")
            assert connection.execute("SELECT count(*) FROM raw.customers").fetchone() is not None
            assert connection.execute(
                "SELECT bool_and(has_table_privilege(current_user, c.oid, 'SELECT') "
                "AND has_table_privilege(current_user, c.oid, 'INSERT') "
                "AND NOT has_table_privilege(current_user, c.oid, "
                "'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='raw' AND c.relkind='r'"
            ).fetchone() == (True,)
            for statement in (
                "SET LOCAL ROLE commercelens_owner",
                "SET LOCAL ROLE commercelens_transformer",
                "SET LOCAL ROLE commercelens_reader",
                "SET LOCAL ROLE postgres",
                "CREATE TABLE raw.__loader_access_probe (id integer)",
                "SELECT count(*) FROM ops.schema_migrations",
                "DELETE FROM raw.customers WHERE false",
                "UPDATE raw.customers SET customer_city='' WHERE false",
                "INSERT INTO ops.source_loads (loaded_by) VALUES ('spoofed')",
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                    connection.execute(statement)
