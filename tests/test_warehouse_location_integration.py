"""Opt-in, read-only physical acceptance of the built location dimension.

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
    os.getenv("COMMERCE_WAREHOUSE_LOCATION_INTEGRATION") != "1",
    reason="Built location dimension checks require explicit opt-in",
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
            "Location physical setup failed; inspect private local configuration.", pytrace=False
        )
    try:
        yield connection
    finally:
        stack.close()


def test_location_view_types_ownership_session_access_domain_and_conservation(
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
        "bool_and(has_table_privilege(current_user, name, 'SELECT') AND "
        "NOT has_table_privilege(current_user, name, "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM unnest(ARRAY['raw.customers','raw.sellers','raw.geolocation']) AS sources(name)"
    ).fetchone() == (True, False, True, True, True)
    assert connection.execute(
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='dim_location'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.dim_location'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == [
        ("zip_code_prefix", "text"),
        ("geolocation_observation_count", "bigint"),
        ("geolocation_city_variant_count", "bigint"),
        ("geolocation_state_variant_count", "bigint"),
        ("outside_broad_brazil_observation_count", "bigint"),
        ("has_geolocation", "boolean"),
        ("is_geolocation_city_ambiguous", "boolean"),
        ("is_geolocation_state_ambiguous", "boolean"),
    ]
    assert connection.execute(
        "WITH domain AS MATERIALIZED ("
        'SELECT customer_zip_code_prefix COLLATE "C" AS zip FROM staging.stg_customers UNION '
        'SELECT seller_zip_code_prefix COLLATE "C" FROM staging.stg_sellers UNION '
        'SELECT geolocation_zip_code_prefix COLLATE "C" FROM staging.stg_geolocation), '
        "actual AS MATERIALIZED (SELECT * FROM core.dim_location), "
        "missing AS (SELECT zip FROM domain EXCEPT ALL SELECT zip_code_prefix FROM actual), "
        "extra AS (SELECT zip_code_prefix FROM actual EXCEPT ALL SELECT zip FROM domain) "
        "SELECT (SELECT count(*) FROM actual)>0, "
        "NOT EXISTS(SELECT 1 FROM missing), NOT EXISTS(SELECT 1 FROM extra), "
        "(SELECT sum(geolocation_observation_count) FROM actual)="
        "(SELECT count(*) FROM staging.stg_geolocation), "
        "(SELECT sum(outside_broad_brazil_observation_count) FROM actual)="
        "(SELECT count(*) FROM staging.stg_geolocation WHERE is_outside_broad_brazil_bounds)"
    ).fetchone() == (True, True, True, True, True)
    # Build a unique geography ZIP domain once, rather than probing a million
    # observations separately for every customer/seller address.
    assert connection.execute(
        "WITH addresses AS ("
        "SELECT 'customers' AS source, customer_zip_code_prefix COLLATE \"C\" AS zip "
        "FROM staging.stg_customers UNION ALL "
        "SELECT 'sellers', seller_zip_code_prefix COLLATE \"C\" FROM staging.stg_sellers), "
        "geography AS MATERIALIZED ("
        'SELECT DISTINCT geolocation_zip_code_prefix COLLATE "C" AS zip '
        "FROM staging.stg_geolocation), "
        "actual AS MATERIALIZED (SELECT * FROM core.dim_location), "
        "expected AS (SELECT a.source, count(*) AS row_count, "
        "count(*) FILTER (WHERE g.zip IS NULL) AS uncovered "
        "FROM addresses a LEFT JOIN geography g ON a.zip=g.zip GROUP BY a.source), "
        "joined AS (SELECT a.source, count(*) AS row_count, "
        "count(*) FILTER (WHERE d.zip_code_prefix IS NULL) AS missing, "
        "count(*) FILTER (WHERE NOT d.has_geolocation) AS uncovered "
        'FROM addresses a LEFT JOIN actual d ON a.zip=d.zip_code_prefix COLLATE "C" '
        "GROUP BY a.source) "
        "SELECT e.source, e.row_count, e.uncovered, e.row_count=j.row_count, "
        "j.missing=0, e.uncovered=j.uncovered "
        "FROM expected e JOIN joined j USING(source) ORDER BY e.source"
    ).fetchall() == [
        ("customers", 99441, 278, True, True, True),
        ("sellers", 3095, 7, True, True, True),
    ]
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.dim_location', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('dim_location__dbt_tmp','dim_location__dbt_backup')"
    ).fetchone() == (0,)
