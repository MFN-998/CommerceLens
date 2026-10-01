"""Read-only acceptance of the built product view; requires explicit opt-in."""

import os

import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_PRODUCT_INTEGRATION") != "1",
    reason="Built product view checks require explicit opt-in",
)


def test_product_view_types_ownership_session_and_access() -> None:
    with connect(load_settings(purpose="transformer")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
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
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute("SELECT current_user").fetchone() == ("commercelens_transformer",)
        assert connection.execute(
            "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
            "has_schema_privilege(current_user, 'raw', 'CREATE'), "
            "has_table_privilege(current_user, 'raw.products', 'SELECT'), "
            "has_table_privilege(current_user, 'raw.products', "
            "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
            "has_schema_privilege(current_user, 'staging', 'USAGE'), "
            "has_schema_privilege(current_user, 'staging', 'CREATE')"
        ).fetchone() == (True, False, True, False, True, True)
        assert connection.execute(
            "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname='stg_products'"
        ).fetchone() == ("v", "commercelens_transformer")
        assert connection.execute(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a WHERE a.attrelid='staging.stg_products'::regclass "
            "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
        ).fetchall() == [
            ("_load_id", "uuid"),
            ("_source_row", "bigint"),
            ("product_id", "text"),
            ("product_category_name", "text"),
            ("product_name_lenght", "bigint"),
            ("product_description_lenght", "bigint"),
            ("product_photos_qty", "bigint"),
            ("product_weight_g", "double precision"),
            ("product_length_cm", "double precision"),
            ("product_height_cm", "double precision"),
            ("product_width_cm", "double precision"),
            ("is_missing_category", "boolean"),
            ("is_missing_name_length", "boolean"),
            ("is_missing_description_length", "boolean"),
            ("is_missing_photos_qty", "boolean"),
            ("is_missing_weight", "boolean"),
            ("is_missing_length", "boolean"),
            ("is_missing_height", "boolean"),
            ("is_missing_width", "boolean"),
            ("is_zero_weight", "boolean"),
        ]
        assert connection.execute(
            "SELECT (SELECT count(*) FROM raw.products)>0 AND "
            "(SELECT count(*) FROM raw.products)=(SELECT count(*) FROM staging.stg_products)"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT count(*), bool_and("
            "NOT has_schema_privilege(rolname, 'staging', 'USAGE,CREATE') "
            "AND NOT has_table_privilege(rolname, 'staging.stg_products', "
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
            "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')"
        ).fetchone() == (3, True)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname IN "
            "('stg_products__dbt_tmp','stg_products__dbt_backup')"
        ).fetchone() == (0,)
