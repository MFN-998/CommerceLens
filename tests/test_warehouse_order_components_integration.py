"""Opt-in, bounded read-only physical acceptance of the order component mart.

The independent oracle groups one long-form child event stream. Full parent
multisets and raw/global reconciliation catch substitutions, fanout and amount
redistribution. Only metadata and aggregate diagnostics leave the database.
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
    os.getenv("COMMERCE_WAREHOUSE_ORDER_COMPONENTS_INTEGRATION") != "1",
    reason="Built order-component checks require explicit opt-in",
)

ORDER_COLUMNS = (
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
)
COMPONENT_COLUMNS = (
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
COLUMNS = ORDER_COLUMNS + COMPONENT_COLUMNS
ORDER_TYPES = (
    "uuid",
    "bigint",
    *("text",) * 3,
    *("timestamp without time zone",) * 5,
    *("boolean",) * 12,
    *("text",) * 4,
    "uuid",
    "bigint",
    *("date",) * 5,
)
COMPONENT_TYPES = (
    "bigint",
    "numeric",
    "numeric",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "numeric",
    "bigint",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "bigint",
    "boolean",
    "boolean",
)
TEXT_COLUMNS = {
    "order_id",
    "customer_id",
    "order_status",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
}
MONEY_MAX = "9999999999999999.99"
HISTORICAL = {
    "item_count": 112650,
    "source_price_sum": Decimal("13591643.70"),
    "source_freight_sum": Decimal("2251909.54"),
    "shipping_before_purchase_count": 0,
    "shipping_beyond_365_days_count": 4,
    "payment_count": 103886,
    "source_payment_sum": Decimal("16008872.12"),
    "zero_installments_count": 2,
    "zero_payment_value_count": 9,
    "undefined_payment_type_count": 3,
    "review_count": 99224,
    "answer_before_creation_count": 0,
    "multiple_review_orders": 547,
}


def _fields(columns: tuple[str, ...]) -> str:
    return ", ".join(
        (column + ' COLLATE "C"' if column in TEXT_COLUMNS else column) + " AS " + column
        for column in columns
    )


def _timestamp(column: str) -> str:
    value = f"nullif({column}, '')"
    return (
        f"CAST(CASE WHEN {value} ~ "
        "'^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) "
        "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' "
        f"AND pg_input_is_valid({value}, 'timestamp without time zone') "
        f'AND {value} COLLATE "C" BETWEEN '
        "'1677-09-21 00:12:44' AND '2262-04-11 23:47:16' "
        f"THEN {value} END AS timestamp without time zone)"
    )


def _numeric(column: str, *, money: bool) -> str:
    pattern = (
        "^[0-9]+([.][0-9]{1,2})?$"
        if money
        else "^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$"
    )
    value = f"nullif({column}, '')"
    return (
        f"CAST(CASE WHEN {value} ~ '{pattern}' "
        f"AND pg_input_is_valid({value}, 'numeric') THEN {value} END AS numeric)"
    )


def _money(column: str) -> str:
    number = _numeric(column, money=True)
    return f"CASE WHEN ({number})<={MONEY_MAX} THEN ({number}) END"


def _source_ctes() -> str:
    # Each nested source view is evaluated once per statement. The independent
    # oracle uses one union and one conditional GROUP BY, not three child joins.
    return (
        f"WITH orders AS MATERIALIZED (SELECT {_fields(ORDER_COLUMNS)} FROM core.fact_orders), "
        f"mart AS MATERIALIZED (SELECT {_fields(COLUMNS)} FROM marts.mart_order_components), "
        'items AS MATERIALIZED (SELECT order_id COLLATE "C" AS order_id, price, freight_value, '
        "is_shipping_before_purchase, is_shipping_beyond_365_days FROM core.fact_order_items), "
        'payments AS MATERIALIZED (SELECT order_id COLLATE "C" AS order_id, payment_value, '
        "is_zero_installments, is_zero_payment_value, is_undefined_payment_type "
        "FROM core.fact_payments), "
        'reviews AS MATERIALIZED (SELECT order_id COLLATE "C" AS order_id, '
        "is_answer_before_creation FROM core.fact_reviews), "
        "events AS MATERIALIZED ("
        "SELECT order_id, 'i'::text AS kind, price AS amount, freight_value AS freight, "
        "is_shipping_before_purchase AS warning_a, is_shipping_beyond_365_days AS warning_b, "
        "false AS warning_c FROM items UNION ALL "
        "SELECT order_id, 'p', payment_value, null::numeric, is_zero_installments, "
        "is_zero_payment_value, is_undefined_payment_type FROM payments UNION ALL "
        "SELECT order_id, 'r', null::numeric, null::numeric, is_answer_before_creation, "
        "false, false FROM reviews), "
        "per_order AS MATERIALIZED (SELECT o.order_id, "
        "count(*) FILTER (WHERE kind='i') AS item_count, "
        "sum(amount) FILTER (WHERE kind='i') AS source_price_sum, "
        "sum(freight) FILTER (WHERE kind='i') AS source_freight_sum, "
        "count(*) FILTER (WHERE kind='i' AND warning_a) AS shipping_before_purchase_count, "
        "count(*) FILTER (WHERE kind='i' AND warning_b) AS shipping_beyond_365_days_count, "
        "count(*) FILTER (WHERE kind='i')>0 AS has_items, "
        "count(*) FILTER (WHERE kind='p') AS payment_count, "
        "sum(amount) FILTER (WHERE kind='p') AS source_payment_sum, "
        "count(*) FILTER (WHERE kind='p' AND warning_a) AS zero_installments_count, "
        "count(*) FILTER (WHERE kind='p' AND warning_b) AS zero_payment_value_count, "
        "count(*) FILTER (WHERE kind='p' AND warning_c) AS undefined_payment_type_count, "
        "count(*) FILTER (WHERE kind='p')>0 AS has_payments, "
        "count(*) FILTER (WHERE kind='r') AS review_count, "
        "count(*) FILTER (WHERE kind='r' AND warning_a) AS answer_before_creation_count, "
        "count(*) FILTER (WHERE kind='r')>0 AS has_reviews, "
        "count(*) FILTER (WHERE kind='r')>1 AS has_multiple_reviews "
        'FROM orders o LEFT JOIN events e ON o.order_id COLLATE "C"=e.order_id COLLATE "C" '
        "GROUP BY o.order_id), "
        "raw_orders AS MATERIALIZED (SELECT nullif(order_id,'') COLLATE \"C\" AS order_id, "
        + _timestamp("order_purchase_timestamp")
        + " AS purchase FROM raw.orders), "
        "raw_items AS MATERIALIZED (SELECT nullif(order_id,'') COLLATE \"C\" AS order_id, "
        + _money("price")
        + " AS price, "
        + _money("freight_value")
        + " AS freight, "
        + _timestamp("shipping_limit_date")
        + " AS shipping FROM raw.order_items), "
        "raw_item_context AS MATERIALIZED (SELECT i.*, o.purchase FROM raw_items i "
        'LEFT JOIN raw_orders o ON i.order_id COLLATE "C"=o.order_id COLLATE "C"), '
        "raw_payment_numbers AS MATERIALIZED (SELECT "
        "nullif(order_id,'') COLLATE \"C\" AS order_id, "
        "nullif(payment_type,'') COLLATE \"C\" AS payment_type, "
        + _money("payment_value")
        + " AS payment_value, "
        + _numeric("payment_installments", money=False)
        + " AS installments "
        "FROM raw.order_payments), "
        "raw_payments AS MATERIALIZED (SELECT order_id, payment_type, payment_value, "
        "CASE WHEN installments=trunc(installments) "
        "AND installments BETWEEN -9223372036854775808 AND 9223372036854775807 "
        "THEN CAST(installments AS bigint) END AS installments FROM raw_payment_numbers), "
        "raw_reviews AS MATERIALIZED (SELECT nullif(order_id,'') COLLATE \"C\" AS order_id, "
        + _timestamp("review_creation_date")
        + " AS created, "
        + _timestamp("review_answer_timestamp")
        + " AS answered FROM raw.order_reviews) "
    )


def _diagnostic(connection: psycopg.Connection, query: str) -> psycopg.Cursor:
    try:
        return connection.execute(query, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Order-component physical query failed; inspect private local configuration.",
            pytrace=False,
        )


@pytest.fixture
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout='55s'")
    except Exception:  # noqa: BLE001 - do not expose private setup details.
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Order-component physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def test_order_component_native_shape_owner_session_and_current_private_access(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    assert _diagnostic(
        connection,
        "SELECT session_user, current_user, current_database(), "
        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())",
    ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
    assert _diagnostic(
        connection,
        "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=session_user",
    ).fetchone() == (True, False, False, False, False, False, False, 2)
    assert _diagnostic(
        connection,
        "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
        "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
        "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user",
    ).fetchall() == [("commercelens_transformer", False, False, True)]
    _diagnostic(connection, "SET LOCAL ROLE commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT current_user, current_setting('transaction_read_only'), "
        "current_setting('statement_timeout')",
    ).fetchone() == ("commercelens_transformer", "on", "55s")
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user,'raw','USAGE'), "
        "has_schema_privilege(current_user,'raw','CREATE'), "
        "has_schema_privilege(current_user,'core','USAGE'), "
        "has_schema_privilege(current_user,'marts','USAGE,CREATE'), "
        "has_table_privilege(current_user,'raw.order_items','SELECT'), "
        "has_table_privilege(current_user,'raw.order_payments','SELECT'), "
        "has_table_privilege(current_user,'raw.order_reviews','SELECT'), "
        "has_table_privilege(current_user,'raw.orders','SELECT')",
    ).fetchone() == (True, False, True, True, True, True, True, True)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='marts' AND c.relname='mart_order_components'",
    ).fetchone() == ("v", "commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT attname, format_type(atttypid,atttypmod) FROM pg_attribute "
        "WHERE attrelid='marts.mart_order_components'::regclass "
        "AND attnum>0 AND NOT attisdropped ORDER BY attnum",
    ).fetchall() == list(zip(COLUMNS, ORDER_TYPES + COMPONENT_TYPES, strict=True))
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(a.atttypid=o.atttypid AND a.atttypmod=o.atttypmod "
        "AND a.attcollation=o.attcollation) FROM pg_attribute a JOIN pg_attribute o "
        "ON o.attrelid='core.fact_orders'::regclass AND o.attname=a.attname "
        "AND o.attnum>0 AND NOT o.attisdropped "
        "WHERE a.attrelid='marts.mart_order_components'::regclass "
        "AND a.attnum BETWEEN 1 AND 33 AND NOT a.attisdropped",
    ).fetchone() == (33, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(atttypid='numeric'::regtype AND atttypmod=-1) "
        "FROM pg_attribute WHERE attrelid='marts.mart_order_components'::regclass "
        "AND attname IN ('source_price_sum','source_freight_sum','source_payment_sum') "
        "AND attnum>0 AND NOT attisdropped",
    ).fetchone() == (3, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname,'marts','CREATE') AND "
        "NOT has_table_privilege(rolname,'marts.mart_order_components', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role')",
    ).fetchone() == (3, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(NOT has_schema_privilege('commercelens_reader',oid, "
        "'USAGE,CREATE')) FROM pg_namespace WHERE nspname IN ('raw','staging','core')",
    ).fetchone() == (3, True)
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege('commercelens_reader','marts','USAGE'), "
        "has_schema_privilege('commercelens_reader','marts','CREATE'), "
        "has_table_privilege('commercelens_reader','marts.mart_order_components','SELECT')",
    ).fetchone() == (True, False, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(NOT has_schema_privilege(rolname,'marts','USAGE,CREATE')) "
        "FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')",
    ).fetchone() == (3, True)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('raw','staging','core','marts') "
        "AND c.relkind IN ('r','p','v','m','f') "
        "AND c.oid<>'marts.mart_order_components'::regclass AND has_table_privilege("
        "'commercelens_reader',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
    ).fetchone() == (0,)
    assert _diagnostic(
        connection,
        "SELECT has_table_privilege('commercelens_reader','marts.mart_order_components', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN,SELECT WITH GRANT OPTION'), "
        "has_any_column_privilege('commercelens_reader','marts.mart_order_components', "
        "'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')",
    ).fetchone() == (False, False)
    assert _diagnostic(
        connection,
        "SELECT (SELECT count(*) FROM pg_class c, "
        "LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a "
        "WHERE c.oid='marts.mart_order_components'::regclass AND a.grantee=0), "
        "(SELECT count(*) FROM pg_namespace n, "
        "LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a "
        "WHERE n.nspname='marts' AND a.grantee=0)",
    ).fetchone() == (0, 0)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='marts' AND c.relname IN "
        "('mart_order_components__dbt_tmp','mart_order_components__dbt_backup')",
    ).fetchone() == (0,)


def test_order_component_full_parent_per_order_children_and_raw_global_conservation(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    _diagnostic(connection, "SET LOCAL ROLE commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT current_user, current_setting('transaction_read_only')",
    ).fetchone() == ("commercelens_transformer", "on")
    diagnostics: list[tuple[str, str, int | Decimal]] = []
    for relation in ("orders", "mart", "per_order", "raw_orders"):
        diagnostics.extend(
            (
                (relation + "_count", f"SELECT count(*) FROM {relation}", 99441),
                (relation + "_keys", f"SELECT count(DISTINCT order_id) FROM {relation}", 99441),
            )
        )
    for expected, actual, columns in (
        ("orders", "mart", ORDER_COLUMNS),
        ("per_order", "mart", ("order_id",) + COMPONENT_COLUMNS),
    ):
        fields = ", ".join(columns)
        for left, right in ((expected, actual), (actual, expected)):
            diagnostics.append(
                (
                    left + "_minus_" + right,
                    (
                        f"SELECT count(*) FROM (SELECT {fields} FROM {left} EXCEPT ALL "
                        f"SELECT {fields} FROM {right}) differences"
                    ),
                    0,
                )
            )
    for relation in ("items", "payments", "reviews", "raw_items", "raw_payments", "raw_reviews"):
        diagnostics.append(
            (
                relation + "_missing_orders",
                f"SELECT count(*) FROM {relation} c WHERE NOT EXISTS (SELECT 1 FROM orders o "
                'WHERE c.order_id COLLATE "C"=o.order_id COLLATE "C")',
                0,
            )
        )
    for relation, condition in (
        ("raw_orders", "purchase IS NULL"),
        (
            "raw_item_context",
            "price IS NULL OR freight IS NULL OR shipping IS NULL OR purchase IS NULL",
        ),
        (
            "raw_payments",
            "payment_value IS NULL OR installments IS NULL OR installments<0 "
            "OR payment_type IS NULL",
        ),
        ("raw_reviews", "created IS NULL OR answered IS NULL"),
        (
            "items",
            "price IS NULL OR freight_value IS NULL OR is_shipping_before_purchase IS NULL "
            "OR is_shipping_beyond_365_days IS NULL",
        ),
        (
            "payments",
            "payment_value IS NULL OR is_zero_installments IS NULL "
            "OR is_zero_payment_value IS NULL OR is_undefined_payment_type IS NULL",
        ),
        ("reviews", "is_answer_before_creation IS NULL"),
    ):
        diagnostics.append(
            (relation + "_invalid_inputs", f"SELECT count(*) FROM {relation} WHERE {condition}", 0)
        )
    for namespace in ("raw", "core", "mart"):
        for field, historical in HISTORICAL.items():
            if namespace == "mart":
                expression = (
                    "count(*) FILTER (WHERE has_multiple_reviews)"
                    if field == "multiple_review_orders"
                    else f"sum({field})"
                )
                query = f"SELECT {expression} FROM mart"
            elif field == "multiple_review_orders":
                relation = "raw_reviews" if namespace == "raw" else "reviews"
                query = (
                    f"SELECT count(*) FROM (SELECT order_id FROM {relation} "
                    "GROUP BY order_id HAVING count(*)>1) multiple_reviews"
                )
            else:
                relation, expression = _global_expression(namespace, field)
                query = f"SELECT {expression} FROM {relation}"
            diagnostics.append((namespace + "_" + field, query, historical))

    domains = []
    for count, presence, amounts, warnings in (
        (
            "item_count",
            "has_items",
            ("source_price_sum", "source_freight_sum"),
            ("shipping_before_purchase_count", "shipping_beyond_365_days_count"),
        ),
        (
            "payment_count",
            "has_payments",
            ("source_payment_sum",),
            ("zero_installments_count", "zero_payment_value_count", "undefined_payment_type_count"),
        ),
        ("review_count", "has_reviews", (), ("answer_before_creation_count",)),
    ):
        domains.extend(
            (f"{count} IS NULL", f"{count}<0", f"{presence} IS DISTINCT FROM ({count}>0)")
        )
        domains.extend(
            f"({warning} IS NULL OR {warning} NOT BETWEEN 0 AND {count})" for warning in warnings
        )
        domains.extend(
            f"(({count}=0 AND {amount} IS NOT NULL) OR ({count}>0 AND "
            f"({amount} IS NULL OR {amount}<0 OR {amount}>{count}*{MONEY_MAX}::numeric)))"
            for amount in amounts
        )
    domains.extend(
        (
            "order_id IS NULL",
            "order_id COLLATE \"C\" !~ '^[0-9a-f]{32}$'",
            "has_multiple_reviews IS DISTINCT FROM (review_count>1)",
        )
    )
    diagnostics.append(
        ("invalid_component_domains", "SELECT count(*) FROM mart WHERE " + " OR ".join(domains), 0)
    )
    result = _diagnostic(
        connection,
        _source_ctes() + "SELECT " + ", ".join(f"({query})" for _, query, _ in diagnostics),
    ).fetchone()
    assert result is not None
    assert dict(zip((name for name, _, _ in diagnostics), result, strict=True)) == {
        name: expected for name, _, expected in diagnostics
    }


def _global_expression(namespace: str, field: str) -> tuple[str, str]:
    raw = namespace == "raw"
    if field in HISTORICAL and field.startswith("shipping_"):
        if raw:
            condition = (
                "shipping<purchase"
                if field == "shipping_before_purchase_count"
                else "shipping-purchase>interval '365 days'"
            )
            return "raw_item_context", f"count(*) FILTER (WHERE {condition})"
        flag = (
            "is_shipping_before_purchase"
            if field == "shipping_before_purchase_count"
            else "is_shipping_beyond_365_days"
        )
        return "items", f"count(*) FILTER (WHERE {flag})"
    mappings = {
        "item_count": ("raw_items" if raw else "items", "count(*)"),
        "source_price_sum": ("raw_items" if raw else "items", "sum(price)"),
        "source_freight_sum": (
            "raw_items" if raw else "items",
            "sum(freight)" if raw else "sum(freight_value)",
        ),
        "payment_count": ("raw_payments" if raw else "payments", "count(*)"),
        "source_payment_sum": ("raw_payments" if raw else "payments", "sum(payment_value)"),
        "zero_installments_count": (
            "raw_payments" if raw else "payments",
            "count(*) FILTER (WHERE installments=0)"
            if raw
            else "count(*) FILTER (WHERE is_zero_installments)",
        ),
        "zero_payment_value_count": (
            "raw_payments" if raw else "payments",
            "count(*) FILTER (WHERE payment_value=0)"
            if raw
            else "count(*) FILTER (WHERE is_zero_payment_value)",
        ),
        "undefined_payment_type_count": (
            "raw_payments" if raw else "payments",
            "count(*) FILTER (WHERE payment_type='not_defined')"
            if raw
            else "count(*) FILTER (WHERE is_undefined_payment_type)",
        ),
        "review_count": ("raw_reviews" if raw else "reviews", "count(*)"),
        "answer_before_creation_count": (
            "raw_reviews" if raw else "reviews",
            "count(*) FILTER (WHERE answered<created)"
            if raw
            else "count(*) FILTER (WHERE is_answer_before_creation)",
        ),
    }
    return mappings[field]
