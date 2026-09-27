"""Read-only acceptance of the built translation view; requires explicit opt-in."""

import os

import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_CATEGORY_TRANSLATION_INTEGRATION") != "1",
    reason="Built category translation view checks require explicit opt-in",
)


def test_category_translation_view_types_ownership_and_access() -> None:
    with connect(load_settings(purpose="transformer")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.execute("SELECT session_user").fetchone() == ("commercelens_transform",)
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute("SELECT current_user").fetchone() == ("commercelens_transformer",)
        assert connection.execute(
            "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname='stg_category_translation'"
        ).fetchone() == ("v", "commercelens_transformer")
        assert connection.execute(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a WHERE a.attrelid='staging.stg_category_translation'::regclass "
            "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
        ).fetchall() == [
            ("_load_id", "uuid"),
            ("_source_row", "bigint"),
            ("product_category_name", "text"),
            ("product_category_name_english", "text"),
        ]
        assert connection.execute(
            "SELECT (SELECT count(*) FROM raw.category_translation)>0 AND "
            "(SELECT count(*) FROM raw.category_translation)="
            "(SELECT count(*) FROM staging.stg_category_translation)"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT count(*), bool_and("
            "NOT has_schema_privilege(rolname, 'staging', 'USAGE,CREATE') "
            "AND NOT has_table_privilege(rolname, 'staging.stg_category_translation', "
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
            "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')"
        ).fetchone() == (3, True)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname IN "
            "('stg_category_translation__dbt_tmp','stg_category_translation__dbt_backup')"
        ).fetchone() == (0,)
