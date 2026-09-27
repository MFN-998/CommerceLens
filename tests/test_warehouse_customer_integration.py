"""Read-only acceptance of the built customer view; requires explicit opt-in."""

import os

import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_CUSTOMER_INTEGRATION") != "1",
    reason="Built customer view checks require explicit opt-in",
)


def test_customer_view_types_ownership_and_access() -> None:
    with connect(load_settings(purpose="transformer")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute(
            "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname='stg_customers'"
        ).fetchone() == ("v", "commercelens_transformer")
        assert connection.execute(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a WHERE a.attrelid='staging.stg_customers'::regclass "
            "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
        ).fetchall() == [
            ("_load_id", "uuid"),
            ("_source_row", "bigint"),
            ("customer_id", "text"),
            ("customer_unique_id", "text"),
            ("customer_zip_code_prefix", "text"),
            ("customer_city", "text"),
            ("customer_state", "text"),
        ]
        assert connection.execute(
            "SELECT (SELECT count(*) FROM raw.customers)>0 AND "
            "(SELECT count(*) FROM raw.customers)=(SELECT count(*) FROM staging.stg_customers)"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT count(*), bool_and("
            "NOT has_schema_privilege(rolname, 'staging', 'USAGE,CREATE') "
            "AND NOT has_table_privilege(rolname, 'staging.stg_customers', "
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
            "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')"
        ).fetchone() == (3, True)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname IN "
            "('stg_customers__dbt_tmp','stg_customers__dbt_backup')"
        ).fetchone() == (0,)
