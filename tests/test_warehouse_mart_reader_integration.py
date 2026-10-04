"""Opt-in, read-only proof of the approved mart reader capability.

The existing administrator assumes a NOLOGIN capability inside one transaction.
This proves its effective permissions, not authentication for a future login.
Only metadata and approved aggregates are fetched; denial probes use savepoints
and write plans without ANALYZE, with no persistent fixtures or data changes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from decimal import Decimal

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_MART_READER_INTEGRATION") != "1",
    reason="Approved mart reader checks require explicit opt-in",
)

COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "is_missing_approval",
    "is_missing_carrier_delivery",
    "is_missing_customer_delivery",
    "is_delivered_missing_approval",
    "is_delivered_missing_carrier_delivery",
    "is_delivered_missing_customer_delivery",
    "is_approval_before_purchase",
    "is_carrier_delivery_before_purchase",
    "is_customer_delivery_before_purchase",
    "is_carrier_delivery_before_approval",
    "is_customer_delivery_before_approval",
    "is_customer_delivery_before_carrier_delivery",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
    "customer_load_id",
    "customer_source_row",
    "purchase_calendar_date",
    "approval_calendar_date",
    "carrier_delivery_calendar_date",
    "customer_delivery_calendar_date",
    "estimated_delivery_calendar_date",
    "item_count",
    "source_price_sum",
    "source_freight_sum",
    "shipping_before_purchase_count",
    "shipping_beyond_365_days_count",
    "has_items",
    "payment_count",
    "source_payment_sum",
    "zero_installments_count",
    "zero_payment_value_count",
    "undefined_payment_type_count",
    "has_payments",
    "review_count",
    "answer_before_creation_count",
    "has_reviews",
    "has_multiple_reviews",
)
TYPE_CODES = (
    2950,
    20,
    *(25,) * 3,
    *(1114,) * 5,
    *(16,) * 12,
    *(25,) * 4,
    2950,
    20,
    *(1082,) * 5,
    20,
    1700,
    1700,
    20,
    20,
    16,
    20,
    1700,
    20,
    20,
    20,
    16,
    20,
    20,
    16,
    16,
)


def _diagnostic(connection: psycopg.Connection, query: str) -> psycopg.Cursor:
    try:
        return connection.execute(query, binary=True)
    except psycopg.Error:
        pytest.fail("Reader query failed; no driver detail logged.", pytrace=False)


@pytest.fixture(scope="module")
def reader_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="admin")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction(force_rollback=True))
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout='55s'")
        connection.execute("SET LOCAL lock_timeout='5s'")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("postgres", "postgres", "postgres", True)
        connection.execute("SET LOCAL ROLE commercelens_reader")
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only'), "
            "current_setting('statement_timeout'), current_setting('lock_timeout')"
        ).fetchone() == ("commercelens_reader", "on", "55s", "5s")
    except Exception:  # noqa: BLE001 - never expose private setup or driver detail.
        with suppress(Exception):
            stack.close()
        pytest.fail("Reader setup failed; inspect private local configuration.", pytrace=False)
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def test_reader_role_and_exact_approved_table_capability(
    reader_connection: psycopg.Connection,
) -> None:
    connection = reader_connection
    assert _diagnostic(
        connection,
        "SELECT session_user, current_user, current_database(), "
        "current_setting('transaction_read_only')",
    ).fetchone() == ("postgres", "commercelens_reader", "postgres", "on")
    assert (
        _diagnostic(
            connection,
            "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
            "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user",
        ).fetchone()
        == (False,) * 7
    )
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
        "WHERE r.rolname=current_user",
    ).fetchone() == (0,)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, r.rolname, NOT EXISTS ("
        "SELECT 1 FROM pg_options_to_table(c.reloptions) o "
        "WHERE o.option_name='security_invoker' AND o.option_value::boolean) "
        "FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner "
        "WHERE c.oid='marts.mart_order_components'::regclass",
    ).fetchone() == ("v", "commercelens_transformer", True)
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user,'marts','USAGE'), "
        "has_schema_privilege(current_user,'marts','CREATE'), "
        "has_table_privilege(current_user,'marts.mart_order_components','SELECT'), "
        "has_table_privilege(current_user,'marts.mart_order_components',"
        "'SELECT WITH GRANT OPTION'), "
        "has_table_privilege(current_user,'marts.mart_order_components',"
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'), "
        "has_any_column_privilege(current_user,'marts.mart_order_components',"
        "'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')",
    ).fetchone() == (True, False, True, False, False, False)
    assert _diagnostic(
        connection,
        "SELECT a.privilege_type, a.is_grantable FROM pg_class c "
        "CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
        "JOIN pg_roles r ON r.oid=a.grantee "
        "WHERE c.oid='marts.mart_order_components'::regclass AND r.rolname=current_user "
        "ORDER BY a.privilege_type",
    ).fetchall() == [("SELECT", False)]


def test_reader_no_off_target_schema_table_or_column_permissions(
    reader_connection: psycopg.Connection,
) -> None:
    connection = reader_connection
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(NOT has_schema_privilege(current_user,n.oid,'CREATE') "
        "AND (n.nspname='marts' OR NOT has_schema_privilege(current_user,n.oid,'USAGE'))) "
        "FROM pg_namespace n WHERE n.nspname IN ('ops','raw','staging','core','marts')",
    ).fetchone() == (5, True)
    assert _diagnostic(
        connection,
        "SELECT count(*)>0, bool_and("
        "NOT has_table_privilege(current_user,c.oid,"
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
        "AND NOT has_any_column_privilege(current_user,c.oid,"
        "'SELECT,INSERT,UPDATE,REFERENCES')) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('ops','raw','staging','core','marts') "
        "AND c.relkind IN ('r','p','v','m','f') "
        "AND c.oid<>'marts.mart_order_components'::regclass",
    ).fetchone() == (True, True)


def test_approved_mart_metadata_and_exact_aggregate_query(
    reader_connection: psycopg.Connection,
) -> None:
    connection = reader_connection
    cursor = _diagnostic(connection, "SELECT * FROM marts.mart_order_components WHERE false")
    assert cursor.fetchall() == []
    assert cursor.description is not None
    assert tuple(column.name for column in cursor.description) == COLUMNS
    assert tuple(column.type_code for column in cursor.description) == TYPE_CODES
    for column in cursor.description:
        if column.type_code == 1700:
            assert (column.precision, column.scale) == (None, None)
    assert _diagnostic(
        connection,
        "SELECT count(*), sum(item_count), sum(payment_count), sum(review_count), "
        "count(*) FILTER (WHERE has_multiple_reviews), sum(source_price_sum), "
        "sum(source_freight_sum), sum(source_payment_sum) "
        "FROM marts.mart_order_components",
    ).fetchone() == (
        99441,
        Decimal("112650"),
        Decimal("103886"),
        Decimal("99224"),
        547,
        Decimal("13591643.70"),
        Decimal("2251909.54"),
        Decimal("16008872.12"),
    )


def test_public_and_api_mart_permissions_remain_denied(
    reader_connection: psycopg.Connection,
) -> None:
    connection = reader_connection
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname,'marts','USAGE,CREATE') "
        "AND NOT has_table_privilege(rolname,'marts.mart_order_components',"
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
        "AND NOT has_any_column_privilege(rolname,'marts.mart_order_components',"
        "'SELECT,INSERT,UPDATE,REFERENCES')) "
        "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')",
    ).fetchone() == (3, True)
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege('public','marts','USAGE,CREATE'), "
        "has_table_privilege('public','marts.mart_order_components',"
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'), "
        "has_any_column_privilege('public','marts.mart_order_components',"
        "'SELECT,INSERT,UPDATE,REFERENCES')",
    ).fetchone() == (False, False, False)


def _expect_permission_denied(connection: psycopg.Connection, statement: str) -> None:
    try:
        # The outer read-only transaction remains usable after an expected denial.
        with connection.transaction():
            connection.execute(statement)
    except psycopg.Error as error:
        if error.sqlstate != "42501":
            pytest.fail("Reader denial probe returned an unexpected SQLSTATE.", pytrace=False)
    else:
        pytest.fail("Reader denial probe unexpectedly succeeded.", pytrace=False)


def test_real_upstream_select_and_plan_only_write_denials(
    reader_connection: psycopg.Connection,
) -> None:
    connection = reader_connection
    for statement in (
        "SELECT count(*) FROM raw.orders",
        "SELECT count(*) FROM staging.stg_orders",
        "SELECT count(*) FROM core.fact_orders",
        "SELECT count(*) FROM ops.schema_migrations",
        "EXPLAIN INSERT INTO raw.orders (order_id) VALUES (NULL)",
        "EXPLAIN UPDATE raw.orders SET order_id=order_id WHERE false",
        "EXPLAIN DELETE FROM raw.orders WHERE false",
    ):
        _expect_permission_denied(connection, statement)
    assert _diagnostic(
        connection,
        "SELECT current_user, current_setting('transaction_read_only'), "
        "has_table_privilege(current_user,'marts.mart_order_components','SELECT')",
    ).fetchone() == ("commercelens_reader", "on", True)
