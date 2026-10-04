"""Opt-in read-only physical acceptance with metadata and aggregate diagnostics.

Independent raw expectations and full seven-field multisets conserve spelling,
addresses and lineage. Parent references use literal existence. No customer IDs,
addresses or other source records are fetched or included in assertions.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_ORDER_CUSTOMERS_INTEGRATION") != "1",
    reason="Built order-customer checks require explicit opt-in",
)

COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
TYPES = ("uuid", "bigint", *("text",) * 5)
STATES = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)


def _fields(*, raw: bool = False) -> str:
    return ", ".join(
        column
        if index < 2
        else (("nullif(" + column + ",'')" if raw else column) + ' COLLATE "C" AS ' + column)
        for index, column in enumerate(COLUMNS)
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
            "Order-customer physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


def test_order_customer_types_collations_ownership_private_access_and_source_conservation(
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
        "WHERE n.nspname='core' AND c.relname='int_order_customers'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.int_order_customers'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))
    assert connection.execute(
        "SELECT count(*), bool_and(a.atttypid=s.atttypid AND a.atttypmod=s.atttypmod "
        "AND a.attcollation=s.attcollation) FROM pg_attribute a JOIN pg_attribute s "
        "ON s.attrelid='staging.stg_customers'::regclass AND s.attname=a.attname "
        "AND s.attnum>0 AND NOT s.attisdropped "
        "WHERE a.attrelid='core.int_order_customers'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped"
    ).fetchone() == (7, True)

    # All five text fields use literal C equality. Raw exact-empty-to-NULL is
    # the established staging rule; source rows and load/ordinal are never chosen.
    counts = connection.execute(
        "WITH raw_expected AS MATERIALIZED (SELECT "
        + _fields(raw=True)
        + " FROM raw.customers), staged AS MATERIALIZED (SELECT "
        + _fields()
        + " FROM staging.stg_customers), actual AS MATERIALIZED (SELECT "
        + _fields()
        + " FROM core.int_order_customers), "
        "raw_missing AS (SELECT * FROM raw_expected EXCEPT ALL SELECT * FROM staged), "
        "raw_extra AS (SELECT * FROM staged EXCEPT ALL SELECT * FROM raw_expected), "
        "missing AS (SELECT * FROM staged EXCEPT ALL SELECT * FROM actual), "
        "extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM staged), "
        "raw_mapping_missing AS (SELECT * FROM raw_expected EXCEPT ALL SELECT * FROM actual), "
        "raw_mapping_extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM raw_expected), "
        "raw_geography AS MATERIALIZED ("
        "SELECT DISTINCT nullif(geolocation_zip_code_prefix,'') COLLATE \"C\" AS zip "
        "FROM raw.geolocation) "
        "SELECT (SELECT count(*) FROM raw_expected), (SELECT count(*) FROM staged), "
        "(SELECT count(*) FROM actual), "
        "(SELECT count(DISTINCT customer_id) FROM raw_expected), "
        "(SELECT count(DISTINCT customer_id) FROM staged), "
        "(SELECT count(DISTINCT customer_id) FROM actual), "
        "(SELECT count(DISTINCT customer_unique_id) FROM raw_expected), "
        "(SELECT count(DISTINCT customer_unique_id) FROM staged), "
        "(SELECT count(DISTINCT customer_unique_id) FROM actual), "
        "(SELECT count(*) FROM raw_missing), (SELECT count(*) FROM raw_extra), "
        "(SELECT count(*) FROM missing), (SELECT count(*) FROM extra), "
        "(SELECT count(*) FROM raw_mapping_missing), (SELECT count(*) FROM raw_mapping_extra), "
        "(SELECT count(*) FROM actual a WHERE NOT EXISTS (SELECT 1 FROM core.dim_customer d "
        'WHERE a.customer_unique_id COLLATE "C"=d.customer_unique_id COLLATE "C")), '
        "(SELECT count(*) FROM actual a WHERE NOT EXISTS (SELECT 1 FROM core.dim_location d "
        'WHERE a.customer_zip_code_prefix COLLATE "C"=d.zip_code_prefix COLLATE "C")), '
        "(SELECT count(*) FROM actual a WHERE EXISTS (SELECT 1 FROM core.dim_location d "
        'WHERE a.customer_zip_code_prefix COLLATE "C"=d.zip_code_prefix COLLATE "C" '
        "AND NOT d.has_geolocation)), "
        "(SELECT count(*) FROM actual a WHERE NOT EXISTS (SELECT 1 FROM raw_geography g "
        'WHERE a.customer_zip_code_prefix COLLATE "C"=g.zip)), '
        "(SELECT count(*) FROM actual a WHERE EXISTS (SELECT 1 FROM core.dim_location d "
        'WHERE a.customer_zip_code_prefix COLLATE "C"=d.zip_code_prefix COLLATE "C" '
        "AND d.has_geolocation IS NULL))",
        binary=True,
    ).fetchone()
    # Accepted source/identity/location evidence: 99,441 order-linked rows,
    # 96,096 repeating cross-order identities and 278 retained uncovered rows.
    assert counts == (99441,) * 6 + (96096,) * 3 + (0,) * 8 + (278, 278, 0)
    assert connection.execute(
        "SELECT count(*) FROM core.int_order_customers WHERE "
        + " OR ".join(column + " IS NULL" for column in COLUMNS)
        + " OR customer_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR customer_unique_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR customer_zip_code_prefix COLLATE \"C\" !~ '^[0-9]{1,5}$' "
        "OR _source_row<1 OR customer_state<>ALL(%s::text[])",
        (list(STATES),),
    ).fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.int_order_customers', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('int_order_customers__dbt_tmp','int_order_customers__dbt_backup')"
    ).fetchone() == (0,)
