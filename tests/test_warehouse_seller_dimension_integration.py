"""Opt-in read-only acceptance of the built seller dimension.

Only schema metadata, aggregate comparisons and warning counts are returned.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_SELLER_DIMENSION_INTEGRATION") != "1",
    reason="Built seller dimension checks require explicit opt-in",
)


@pytest.fixture
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Seller dimension physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


def test_seller_dimension_types_ownership_session_access_and_source_conservation(
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
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.sellers', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.sellers', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
    ).fetchone() == (True, False, True, True, True, False)
    assert connection.execute(
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='dim_seller'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.dim_seller'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == [
        ("_load_id", "uuid"),
        ("_source_row", "bigint"),
        ("seller_id", "text"),
        ("seller_zip_code_prefix", "text"),
        ("seller_city", "text"),
        ("seller_state", "text"),
        ("has_geolocation", "boolean"),
    ]
    # Compare complete rows and multiplicities without exposing source values.
    # Aggregate geography to its unique ZIP domain before the source comparison.
    assert connection.execute(
        "WITH raw_expected AS MATERIALIZED ("
        "SELECT _load_id, _source_row, nullif(seller_id,'') AS seller_id, "
        "nullif(seller_zip_code_prefix,'') AS seller_zip_code_prefix, "
        "nullif(seller_city,'') AS seller_city, nullif(seller_state,'') AS seller_state "
        "FROM raw.sellers), staged AS MATERIALIZED (SELECT * FROM staging.stg_sellers), "
        "actual AS MATERIALIZED (SELECT * FROM core.dim_seller), "
        "geography AS MATERIALIZED ("
        'SELECT DISTINCT geolocation_zip_code_prefix COLLATE "C" AS zip '
        "FROM staging.stg_geolocation), expected AS MATERIALIZED ("
        "SELECT s.*, g.zip IS NOT NULL AS has_geolocation FROM staged s "
        'LEFT JOIN geography g ON s.seller_zip_code_prefix COLLATE "C"=g.zip), '
        "raw_missing AS (SELECT * FROM raw_expected EXCEPT ALL SELECT * FROM staged), "
        "raw_extra AS (SELECT * FROM staged EXCEPT ALL SELECT * FROM raw_expected), "
        "missing AS (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual), "
        "extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected), "
        "location_join AS MATERIALIZED ("
        "SELECT s.seller_id, d.zip_code_prefix, d.has_geolocation FROM staged s "
        "LEFT JOIN core.dim_location d "
        'ON s.seller_zip_code_prefix COLLATE "C"=d.zip_code_prefix COLLATE "C") '
        "SELECT (SELECT count(*) FROM raw_expected), (SELECT count(*) FROM staged), "
        "(SELECT count(*) FROM actual), (SELECT count(DISTINCT seller_id) FROM actual), "
        "(SELECT count(*) FROM actual WHERE NOT has_geolocation), "
        "(SELECT count(*) FROM actual WHERE has_geolocation IS NULL), "
        "NOT EXISTS(SELECT 1 FROM raw_missing), NOT EXISTS(SELECT 1 FROM raw_extra), "
        "NOT EXISTS(SELECT 1 FROM missing), NOT EXISTS(SELECT 1 FROM extra), "
        "(SELECT count(*) FROM location_join), "
        "(SELECT count(*) FROM location_join WHERE zip_code_prefix IS NULL), "
        "(SELECT count(*) FROM location_join WHERE NOT has_geolocation)"
    ).fetchone() == (3095, 3095, 3095, 3095, 7, 0, True, True, True, True, 3095, 0, 7)
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.dim_seller', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('dim_seller__dbt_tmp','dim_seller__dbt_backup')"
    ).fetchone() == (0,)
