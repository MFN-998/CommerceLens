"""Opt-in read-only acceptance of the built customer identity dimension.

Only schema metadata and aggregate comparisons are returned. No customer
identifiers or source addresses are fetched, printed or included in assertions.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_CUSTOMER_DIMENSION_INTEGRATION") != "1",
    reason="Built customer dimension checks require explicit opt-in",
)


@pytest.fixture
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Customer dimension physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


def test_customer_identity_types_ownership_session_access_and_source_conservation(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    assert connection.execute(
        "SELECT session_user, current_user, current_database(), "
        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
    ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
    assert connection.execute(
        "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=session_user"
    ).fetchone() == (True, False, False, False, False, False, False, 2)
    assert connection.execute(
        "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
        "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
        "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user"
    ).fetchall() == [("commercelens_transformer", False, False, True)]
    connection.execute("SET LOCAL ROLE commercelens_transformer")
    assert connection.execute(
        "SELECT current_user, current_setting('transaction_read_only')"
    ).fetchone() == ("commercelens_transformer", "on")
    assert connection.execute(
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.customers', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.customers', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
    ).fetchone() == (True, False, True, True, True, True, False)
    assert connection.execute(
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='dim_customer'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod), n.nspname, c.collname "
        "FROM pg_attribute a LEFT JOIN pg_collation c ON c.oid=a.attcollation "
        "LEFT JOIN pg_namespace n ON n.oid=c.collnamespace "
        "WHERE a.attrelid='core.dim_customer'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == [("customer_unique_id", "text", "pg_catalog", "C")]
    # Full raw-to-staging rows include lineage and all address fields. Each text
    # field uses the documented exact-empty-to-null rule, with literal C equality.
    # Independently derive identity from raw spelling and that boundary rule.
    counts = connection.execute(
        "WITH raw_expected AS MATERIALIZED ("
        "SELECT _load_id, _source_row, "
        "nullif(customer_id,'') COLLATE \"C\" AS customer_id, "
        "nullif(customer_unique_id,'') COLLATE \"C\" AS customer_unique_id, "
        "nullif(customer_zip_code_prefix,'') COLLATE \"C\" AS customer_zip_code_prefix, "
        "nullif(customer_city,'') COLLATE \"C\" AS customer_city, "
        "nullif(customer_state,'') COLLATE \"C\" AS customer_state FROM raw.customers), "
        "staged AS MATERIALIZED (SELECT _load_id, _source_row, "
        'customer_id COLLATE "C", customer_unique_id COLLATE "C", '
        'customer_zip_code_prefix COLLATE "C", customer_city COLLATE "C", '
        'customer_state COLLATE "C" FROM staging.stg_customers), '
        "raw_identities AS MATERIALIZED ("
        "SELECT DISTINCT nullif(customer_unique_id,'') COLLATE \"C\" AS customer_unique_id "
        "FROM raw.customers), staged_identities AS MATERIALIZED ("
        'SELECT DISTINCT customer_unique_id COLLATE "C" AS customer_unique_id FROM staged), '
        "actual AS MATERIALIZED ("
        'SELECT customer_unique_id COLLATE "C" AS customer_unique_id FROM core.dim_customer), '
        "raw_missing AS (SELECT * FROM raw_expected EXCEPT ALL SELECT * FROM staged), "
        "raw_extra AS (SELECT * FROM staged EXCEPT ALL SELECT * FROM raw_expected), "
        "stage_missing AS ("
        "SELECT * FROM raw_identities EXCEPT ALL SELECT * FROM staged_identities), "
        "stage_extra AS ("
        "SELECT * FROM staged_identities EXCEPT ALL SELECT * FROM raw_identities), "
        "missing AS (SELECT * FROM staged_identities EXCEPT ALL SELECT * FROM actual), "
        "extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM staged_identities), "
        "raw_dimension_missing AS ("
        "SELECT * FROM raw_identities EXCEPT ALL SELECT * FROM actual), "
        "raw_dimension_extra AS ("
        "SELECT * FROM actual EXCEPT ALL SELECT * FROM raw_identities) "
        "SELECT (SELECT count(*) FROM raw_expected), (SELECT count(*) FROM staged), "
        "(SELECT count(*) FROM raw_identities), (SELECT count(*) FROM staged_identities), "
        "(SELECT count(*) FROM actual), "
        "(SELECT count(*) FROM (SELECT DISTINCT customer_unique_id FROM actual) identities), "
        "(SELECT count(*) FROM raw_missing), (SELECT count(*) FROM raw_extra), "
        "(SELECT count(*) FROM stage_missing), (SELECT count(*) FROM stage_extra), "
        "(SELECT count(*) FROM missing), (SELECT count(*) FROM extra), "
        "(SELECT count(*) FROM raw_dimension_missing), (SELECT count(*) FROM raw_dimension_extra)"
    ).fetchone()
    assert counts is not None
    assert counts[:2] == (99441, 99441)
    assert counts[2] > 0
    # Verified snapshot baseline: docs/data-quality-report.json records 96,096
    # distinct/non-null customer_unique_id values and zero nulls (2026-09-20).
    assert counts[2:6] == (96096, 96096, 96096, 96096)
    assert counts[6:] == (0,) * 8
    assert connection.execute(
        "SELECT (SELECT count(*) FROM raw.customers WHERE customer_unique_id IS NULL "
        "OR customer_unique_id COLLATE \"C\" !~ '^[0-9a-f]{32}$'), "
        "(SELECT count(*) FROM staging.stg_customers WHERE customer_unique_id IS NULL "
        "OR customer_unique_id COLLATE \"C\" !~ '^[0-9a-f]{32}$'), "
        "(SELECT count(*) FROM core.dim_customer WHERE customer_unique_id IS NULL "
        "OR customer_unique_id COLLATE \"C\" !~ '^[0-9a-f]{32}$')"
    ).fetchone() == (0, 0, 0)
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'raw', 'USAGE,CREATE') AND "
        "NOT has_schema_privilege(rolname, 'staging', 'USAGE,CREATE') AND "
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'raw.customers', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AND "
        "NOT has_table_privilege(rolname, 'staging.stg_customers', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AND "
        "NOT has_table_privilege(rolname, 'core.dim_customer', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('dim_customer__dbt_tmp','dim_customer__dbt_backup')"
    ).fetchone() == (0,)
