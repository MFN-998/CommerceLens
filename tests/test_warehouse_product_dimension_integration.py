"""Opt-in read-only physical acceptance using metadata and aggregate evidence.

No source identifiers, categories, English labels or physical measures are fetched.
Full SQL multiset comparisons preserve exact doubles without textual transport.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_PRODUCT_DIMENSION_INTEGRATION") != "1",
    reason="Built product dimension checks require explicit opt-in",
)

SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
    "is_missing_category",
    "is_missing_name_length",
    "is_missing_description_length",
    "is_missing_photos_qty",
    "is_missing_weight",
    "is_missing_length",
    "is_missing_height",
    "is_missing_width",
    "is_zero_weight",
)
COLUMNS = (*SOURCE_COLUMNS, "product_category_name_english", "is_untranslated_category")
TYPES = (
    "uuid",
    "bigint",
    "text",
    "text",
    *("bigint",) * 3,
    *("double precision",) * 4,
    *("boolean",) * 9,
    "text",
    "boolean",
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
            "Product dimension physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


def test_product_types_ownership_session_private_access_and_complete_source_conservation(
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
        "has_table_privilege(current_user, 'raw.products', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.category_translation', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.products', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
        "has_table_privilege(current_user, 'raw.category_translation', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
    ).fetchone() == (True, False, True, True, True, True, True, False, False)
    assert connection.execute(
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='dim_product'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.dim_product'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))

    # The complete expected projection includes all 20 staged fields unchanged.
    # Raw key/English expectations independently verify the staging boundary and
    # literal lookup. Every diagnostic fetched below is a count, never a row value.
    text_columns = {"product_id", "product_category_name", "product_category_name_english"}
    source_fields = ", ".join(
        "s." + column + (' COLLATE "C" AS ' + column if column in text_columns else "")
        for column in SOURCE_COLUMNS
    )
    actual_fields = ", ".join(
        column + (' COLLATE "C" AS ' + column if column in text_columns else "")
        for column in COLUMNS
    )
    counts = connection.execute(
        "WITH staged AS MATERIALIZED (SELECT "
        + ", ".join(SOURCE_COLUMNS)
        + " FROM staging.stg_products), expected AS MATERIALIZED (SELECT "
        + source_fields
        + ', t.product_category_name_english COLLATE "C" AS product_category_name_english, '
        "s.product_category_name IS NOT NULL AND t.product_category_name IS NULL "
        "AS is_untranslated_category FROM staged s "
        "LEFT JOIN staging.stg_category_translation t "
        'ON s.product_category_name COLLATE "C"=t.product_category_name COLLATE "C"), '
        "actual AS MATERIALIZED (SELECT " + actual_fields + " FROM core.dim_product), "
        "missing AS (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual), "
        "extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected), "
        "raw_products AS MATERIALIZED (SELECT _load_id, _source_row, "
        "nullif(product_id,'') COLLATE \"C\" AS product_id, "
        "nullif(product_category_name,'') COLLATE \"C\" AS product_category_name "
        "FROM raw.products), "
        "staged_keys AS MATERIALIZED (SELECT _load_id, _source_row, "
        'product_id COLLATE "C", product_category_name COLLATE "C" FROM staged), '
        "raw_translation AS MATERIALIZED (SELECT _load_id, _source_row, "
        "nullif(product_category_name,'') COLLATE \"C\" AS product_category_name, "
        "nullif(product_category_name_english,'') COLLATE \"C\" AS product_category_name_english "
        "FROM raw.category_translation), staged_translation AS MATERIALIZED ("
        'SELECT _load_id, _source_row, product_category_name COLLATE "C", '
        'product_category_name_english COLLATE "C" FROM staging.stg_category_translation), '
        "raw_enriched AS MATERIALIZED (SELECT p.*, t.product_category_name_english, "
        "p.product_category_name IS NOT NULL AND t.product_category_name IS NULL "
        "AS is_untranslated_category FROM raw_products p "
        "LEFT JOIN raw_translation t ON p.product_category_name=t.product_category_name), "
        "actual_enriched AS MATERIALIZED (SELECT _load_id, _source_row, "
        'product_id COLLATE "C", product_category_name COLLATE "C", '
        'product_category_name_english COLLATE "C", is_untranslated_category FROM actual), '
        "raw_key_missing AS (SELECT * FROM raw_products EXCEPT ALL SELECT * FROM staged_keys), "
        "raw_key_extra AS (SELECT * FROM staged_keys EXCEPT ALL SELECT * FROM raw_products), "
        "translation_missing AS ("
        "SELECT * FROM raw_translation EXCEPT ALL SELECT * FROM staged_translation), "
        "translation_extra AS ("
        "SELECT * FROM staged_translation EXCEPT ALL SELECT * FROM raw_translation), "
        "raw_enrichment_missing AS ("
        "SELECT * FROM raw_enriched EXCEPT ALL SELECT * FROM actual_enriched), "
        "raw_enrichment_extra AS ("
        "SELECT * FROM actual_enriched EXCEPT ALL SELECT * FROM raw_enriched) "
        "SELECT (SELECT count(*) FROM raw_products), (SELECT count(*) FROM staged), "
        "(SELECT count(*) FROM actual), (SELECT count(DISTINCT product_id) FROM actual), "
        "(SELECT count(*) FROM expected), (SELECT count(*) FROM raw_enriched), "
        "(SELECT count(*) FROM missing), (SELECT count(*) FROM extra), "
        "(SELECT count(*) FROM raw_key_missing), (SELECT count(*) FROM raw_key_extra), "
        "(SELECT count(*) FROM translation_missing), (SELECT count(*) FROM translation_extra), "
        "(SELECT count(*) FROM raw_enrichment_missing), "
        "(SELECT count(*) FROM raw_enrichment_extra), "
        "(SELECT count(*) FROM raw_products WHERE product_category_name IS NULL), "
        "(SELECT count(*) FROM raw_enriched WHERE is_untranslated_category)",
        binary=True,
    ).fetchone()
    assert counts == (32951,) * 6 + (0,) * 8 + (610, 13)

    mandatory = (*COLUMNS[:3], *COLUMNS[11:20], "is_untranslated_category")
    null_predicate = " OR ".join(column + " IS NULL" for column in mandatory)
    assert connection.execute(
        "SELECT count(*) FROM core.dim_product WHERE "
        + null_predicate
        + " OR product_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' OR _source_row<1 "
        "OR is_missing_category IS DISTINCT FROM (product_category_name IS NULL) "
        "OR (product_category_name IS NULL AND (product_category_name_english IS NOT NULL "
        "OR is_untranslated_category)) "
        "OR (is_untranslated_category AND (product_category_name IS NULL "
        "OR product_category_name_english IS NOT NULL)) "
        "OR (product_category_name IS NOT NULL AND NOT is_untranslated_category "
        "AND product_category_name_english IS NULL)"
    ).fetchone() == (0,)
    # Stored staging acceptance (2026-10-01) verifies these exact diagnostic
    # counts; the Phase 2 report also verifies 13 nonempty untranslated products.
    assert connection.execute(
        "SELECT count(*) FILTER (WHERE is_missing_category), "
        "count(*) FILTER (WHERE is_untranslated_category), "
        "count(*) FILTER (WHERE is_zero_weight), "
        "count(*) FILTER (WHERE product_weight_g=0) FROM core.dim_product"
    ).fetchone() == (610, 13, 4, 4)
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.dim_product', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('dim_product__dbt_tmp','dim_product__dbt_backup')"
    ).fetchone() == (0,)
