"""Read-only physical acceptance of the built review view; requires explicit opt-in."""

import os

import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_REVIEW_INTEGRATION") != "1",
    reason="Built review view checks require explicit opt-in",
)


def test_review_view_types_ownership_session_and_access() -> None:
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
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only')"
        ).fetchone() == ("commercelens_transformer", "on")
        assert connection.execute(
            "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
            "has_schema_privilege(current_user, 'raw', 'CREATE'), "
            "has_table_privilege(current_user, 'raw.order_reviews', 'SELECT'), "
            "has_table_privilege(current_user, 'raw.order_reviews', "
            "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
            "has_schema_privilege(current_user, 'staging', 'USAGE'), "
            "has_schema_privilege(current_user, 'staging', 'CREATE')"
        ).fetchone() == (True, False, True, False, True, True)
        assert connection.execute(
            "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname='stg_order_reviews'"
        ).fetchone() == ("v", "commercelens_transformer")
        assert connection.execute(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a WHERE a.attrelid='staging.stg_order_reviews'::regclass "
            "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
        ).fetchall() == [
            ("_load_id", "uuid"),
            ("_source_row", "bigint"),
            ("review_id", "text"),
            ("order_id", "text"),
            ("review_score", "bigint"),
            ("review_comment_title", "text"),
            ("review_comment_message", "text"),
            ("review_creation_date", "timestamp without time zone"),
            ("review_answer_timestamp", "timestamp without time zone"),
            ("is_answer_before_creation", "boolean"),
        ]
        assert connection.execute(
            "SELECT (SELECT count(*) FROM raw.order_reviews)>0 AND "
            "(SELECT count(*) FROM raw.order_reviews)="
            "(SELECT count(*) FROM staging.stg_order_reviews)"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT "
            "(SELECT count(*) FROM raw.order_reviews WHERE "
            "review_answer_timestamp::timestamp without time zone < "
            "review_creation_date::timestamp without time zone)="
            "(SELECT count(*) FROM staging.stg_order_reviews WHERE is_answer_before_creation), "
            "(SELECT count(*) FROM raw.order_reviews WHERE "
            "nullif(review_comment_title, '') IS NULL)="
            "(SELECT count(*) FROM staging.stg_order_reviews WHERE review_comment_title IS NULL), "
            "(SELECT count(*) FROM raw.order_reviews WHERE "
            "nullif(review_comment_message, '') IS NULL)="
            "(SELECT count(*) FROM staging.stg_order_reviews WHERE review_comment_message IS NULL)"
        ).fetchone() == (True, True, True)
        assert connection.execute(
            "SELECT count(*), bool_and("
            "NOT has_schema_privilege(rolname, 'staging', 'USAGE,CREATE') "
            "AND NOT has_table_privilege(rolname, 'staging.stg_order_reviews', "
            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
            "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')"
        ).fetchone() == (3, True)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='staging' AND c.relname IN "
            "('stg_order_reviews__dbt_tmp','stg_order_reviews__dbt_backup')"
        ).fetchone() == (0,)
