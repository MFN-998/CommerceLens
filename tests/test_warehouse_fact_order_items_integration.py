"""Opt-in, aggregate-only physical acceptance of the private item fact view.

Independent raw guards preserve exact source money, item attributes and both
lineages. Only counts, sums and metadata leave the read-only transaction; source
records and private connection errors never appear in assertions.
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
    os.getenv("COMMERCE_WAREHOUSE_FACT_ITEMS_INTEGRATION") != "1",
    reason="Built item-fact checks require explicit opt-in",
)

ITEM_COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
)
ORDER_COLUMNS = ("_load_id", "_source_row", "order_id", "order_purchase_timestamp")
CONTEXT_COLUMNS = ("order_purchase_timestamp", "order_load_id", "order_source_row")
FLAGS = ("is_shipping_before_purchase", "is_shipping_beyond_365_days")
COLUMNS = ITEM_COLUMNS + CONTEXT_COLUMNS + FLAGS + ("shipping_calendar_date",)
TYPES = (
    "uuid",
    "bigint",
    "text",
    "bigint",
    "text",
    "text",
    "timestamp without time zone",
    "numeric(18,2)",
    "numeric(18,2)",
    "timestamp without time zone",
    "uuid",
    "bigint",
    "boolean",
    "boolean",
    "date",
)
TEXT_COLUMNS = {"order_id", "product_id", "seller_id"}
MONEY_MAX = "9999999999999999.99"
MONEY_SUMS = (Decimal("13591643.70"), Decimal("2251909.54"))
DECIMAL_PATTERN = "^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$"


def _fields(columns: tuple[str, ...]) -> str:
    return ", ".join(
        (column + ' COLLATE "C"' if column in TEXT_COLUMNS else column) + " AS " + column
        for column in columns
    )


def _valid_timestamp(column: str) -> str:
    return (
        f"({column} ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) "
        "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' "
        f"AND pg_input_is_valid({column}, 'timestamp without time zone') "
        f'AND {column} COLLATE "C" BETWEEN '
        "'1677-09-21 00:12:44' AND '2262-04-11 23:47:16')"
    )


def _timestamp(column: str) -> str:
    return (
        f"CAST(CASE WHEN {_valid_timestamp(column)} THEN {column} END "
        "AS timestamp without time zone)"
    )


def _numeric(column: str, *, money: bool) -> str:
    pattern = "^[0-9]+([.][0-9]{1,2})?$" if money else DECIMAL_PATTERN
    return (
        f"CAST(CASE WHEN {column} ~ '{pattern}' "
        f"AND pg_input_is_valid({column}, 'numeric') THEN {column} END AS numeric)"
    )


def _valid_ordinal(column: str) -> str:
    return (
        f"({column} IS NOT NULL AND {column}=trunc({column}) "
        f"AND {column} BETWEEN -9223372036854775808 AND 9223372036854775807)"
    )


def _fact_projection(items: str, orders: str) -> str:
    return (
        "SELECT "
        + ", ".join(f"i.{column}" for column in ITEM_COLUMNS)
        + ", o.order_purchase_timestamp, o._load_id AS order_load_id, "
        "o._source_row AS order_source_row, "
        "COALESCE(i.shipping_limit_date<o.order_purchase_timestamp, false) "
        "AS is_shipping_before_purchase, "
        "COALESCE(i.shipping_limit_date-o.order_purchase_timestamp>interval '365 days', false) "
        "AS is_shipping_beyond_365_days, "
        "CAST(i.shipping_limit_date AS date) AS shipping_calendar_date "
        f"FROM {items} i LEFT JOIN {orders} o "
        'ON i.order_id COLLATE "C"=o.order_id COLLATE "C"'
    )


def _source_ctes() -> str:
    normalized = ", ".join(
        column if index < 2 else f"nullif({column}, '') AS {column}"
        for index, column in enumerate(ITEM_COLUMNS)
    )
    typed = (
        '_load_id, _source_row, order_id COLLATE "C" AS order_id, '
        f"CASE WHEN {_valid_ordinal('item_number')} THEN CAST(item_number AS bigint) "
        'END AS order_item_id, product_id COLLATE "C" AS product_id, '
        'seller_id COLLATE "C" AS seller_id, '
        + _timestamp("shipping_limit_date")
        + " AS shipping_limit_date, "
        f"CAST(CASE WHEN price_number<={MONEY_MAX} THEN price_number END AS numeric(18,2)) "
        "AS price, "
        f"CAST(CASE WHEN freight_number<={MONEY_MAX} THEN freight_number END AS numeric(18,2)) "
        "AS freight_value"
    )
    return (
        f"WITH raw_item_normalized AS MATERIALIZED (SELECT {normalized} FROM raw.order_items), "
        "raw_item_numeric AS MATERIALIZED (SELECT *, "
        + _numeric("order_item_id", money=False)
        + " AS item_number, "
        + _numeric("price", money=True)
        + " AS price_number, "
        + _numeric("freight_value", money=True)
        + " AS freight_number "
        "FROM raw_item_normalized), "
        f"raw_items AS MATERIALIZED (SELECT {typed} FROM raw_item_numeric), "
        "raw_order_normalized AS MATERIALIZED (SELECT _load_id, _source_row, "
        "nullif(order_id, '') COLLATE \"C\" AS order_id, "
        "nullif(order_purchase_timestamp, '') AS order_purchase_timestamp FROM raw.orders), "
        "raw_orders AS MATERIALIZED (SELECT _load_id, _source_row, order_id, "
        + _timestamp("order_purchase_timestamp")
        + " AS order_purchase_timestamp "
        "FROM raw_order_normalized), "
        f"staged_items AS MATERIALIZED (SELECT {_fields(ITEM_COLUMNS)} "
        "FROM staging.stg_order_items), "
        f"staged_orders AS MATERIALIZED (SELECT {_fields(ORDER_COLUMNS)} "
        "FROM staging.stg_orders), "
        f"order_facts AS MATERIALIZED (SELECT {_fields(ORDER_COLUMNS)} FROM core.fact_orders), "
        f"raw_expected AS MATERIALIZED ({_fact_projection('raw_items', 'raw_orders')}), "
        "staged_expected AS MATERIALIZED ("
        + _fact_projection("staged_items", "order_facts")
        + "), "
        f"actual AS MATERIALIZED (SELECT {_fields(COLUMNS)} FROM core.fact_order_items) "
    )


def _diagnostic(
    connection: psycopg.Connection,
    query: str,
    params: tuple[object, ...] | None = None,
) -> psycopg.Cursor:
    try:
        return connection.execute(query, params, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Item-fact physical diagnostic query failed; inspect private local configuration.",
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
    except Exception:  # noqa: BLE001 - setup failures must not reveal private connection details.
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Item-fact physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def test_item_fact_native_types_inherited_metadata_session_and_private_access(
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
        "SELECT current_user, current_setting('transaction_read_only')",
    ).fetchone() == ("commercelens_transformer", "on")
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.order_items', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.order_items', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
        "has_table_privilege(current_user, 'raw.orders', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.orders', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
    ).fetchone() == (True, False, True, True, True, True, False, True, False)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='fact_order_items'",
    ).fetchone() == ("v", "commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.fact_order_items'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))
    inherited = tuple((name, "staging.stg_order_items", name) for name in ITEM_COLUMNS) + (
        ("order_purchase_timestamp", "core.fact_orders", "order_purchase_timestamp"),
        ("order_load_id", "core.fact_orders", "_load_id"),
        ("order_source_row", "core.fact_orders", "_source_row"),
    )
    inherited_values = ", ".join("(%s::text,%s::text,%s::text)" for _ in inherited)
    assert _diagnostic(
        connection,
        "WITH inherited(fact_name, source_relation, source_name) AS (VALUES "
        + inherited_values
        + ") SELECT count(*), bool_and(a.atttypid=s.atttypid AND a.atttypmod=s.atttypmod "
        "AND a.attcollation=s.attcollation) FROM inherited i JOIN pg_attribute a "
        "ON a.attrelid='core.fact_order_items'::regclass AND a.attname=i.fact_name "
        "AND a.attnum>0 AND NOT a.attisdropped JOIN pg_attribute s "
        "ON s.attrelid=to_regclass(i.source_relation) AND s.attname=i.source_name "
        "AND s.attnum>0 AND NOT s.attisdropped",
        tuple(value for row in inherited for value in row),
    ).fetchone() == (12, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.fact_order_items', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')",
    ).fetchone() == (4, True)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('fact_order_items__dbt_tmp','fact_order_items__dbt_backup')",
    ).fetchone() == (0,)


def test_item_fact_independent_raw_conservation_exact_money_context_and_parents(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    _diagnostic(connection, "SET LOCAL ROLE commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT current_user, current_setting('transaction_read_only')",
    ).fetchone() == ("commercelens_transformer", "on")
    counts: list[tuple[str, str, int]] = []
    for relation in ("raw_items", "staged_items", "raw_expected", "staged_expected", "actual"):
        counts.extend(
            (
                (relation + "_count", f"SELECT count(*) FROM {relation}", 112650),
                (
                    relation + "_grain",
                    f"SELECT count(*) FROM (SELECT order_id, order_item_id "
                    f"FROM {relation} GROUP BY order_id, order_item_id) item_grain",
                    112650,
                ),
            )
        )
    for relation in ("raw_orders", "staged_orders", "order_facts"):
        counts.extend(
            (
                (relation + "_count", f"SELECT count(*) FROM {relation}", 99441),
                (
                    relation + "_order_ids",
                    f"SELECT count(DISTINCT order_id) FROM {relation}",
                    99441,
                ),
            )
        )
    for left, right in (
        ("raw_items", "staged_items"),
        ("raw_orders", "staged_orders"),
        ("staged_orders", "order_facts"),
        ("raw_orders", "order_facts"),
        ("raw_expected", "staged_expected"),
        ("staged_expected", "actual"),
        ("raw_expected", "actual"),
    ):
        for expected, observed in ((left, right), (right, left)):
            counts.append(
                (
                    expected + "_minus_" + observed,
                    (
                        f"SELECT count(*) FROM (SELECT * FROM {expected} EXCEPT ALL "
                        f"SELECT * FROM {observed}) differences"
                    ),
                    0,
                )
            )
    rejected_item_fields = (
        f"(order_item_id IS NOT NULL AND NOT {_valid_ordinal('item_number')}) OR "
        f"(shipping_limit_date IS NOT NULL AND NOT {_valid_timestamp('shipping_limit_date')}) OR "
        f"(price IS NOT NULL AND (price_number IS NULL OR price_number>{MONEY_MAX})) OR "
        f"(freight_value IS NOT NULL AND (freight_number IS NULL OR freight_number>{MONEY_MAX}))"
    )
    counts.extend(
        (
            (
                "rejected_nonempty_item_fields",
                f"SELECT count(*) FROM raw_item_numeric WHERE {rejected_item_fields}",
                0,
            ),
            (
                "rejected_nonempty_purchase",
                "SELECT count(*) FROM raw_order_normalized "
                "WHERE order_purchase_timestamp IS NOT NULL "
                f"AND NOT {_valid_timestamp('order_purchase_timestamp')}",
                0,
            ),
            (
                "invalid_raw_items",
                "SELECT count(*) FROM raw_items WHERE "
                + " OR ".join(column + " IS NULL" for column in ITEM_COLUMNS)
                + " OR _source_row<1 OR order_item_id<1",
                0,
            ),
            (
                "invalid_raw_order_context",
                "SELECT count(*) FROM raw_orders WHERE "
                + " OR ".join(column + " IS NULL" for column in ORDER_COLUMNS)
                + " OR _source_row<1",
                0,
            ),
        )
    )
    result = _diagnostic(
        connection,
        _source_ctes() + "SELECT " + ", ".join(f"({query})" for _, query, _ in counts),
    ).fetchone()
    assert result is not None
    assert dict(zip((name for name, _, _ in counts), result, strict=True)) == {
        name: expected for name, _, expected in counts
    }
    assert (
        _diagnostic(
            connection,
            _source_ctes()
            + " UNION ALL ".join(
                f"SELECT sum(price), sum(freight_value) FROM {relation}"
                for relation in (
                    "raw_items",
                    "staged_items",
                    "raw_expected",
                    "staged_expected",
                    "actual",
                )
            ),
        ).fetchall()
        == [MONEY_SUMS] * 5
    )

    # The raw join independently establishes both contextual counts. The accepted
    # source quality report records zero reversed deadlines and four beyond 365 days.
    assert (
        _diagnostic(
            connection,
            _source_ctes()
            + " UNION ALL ".join(
                "SELECT count(*) FILTER (WHERE is_shipping_before_purchase), "
                f"count(*) FILTER (WHERE is_shipping_beyond_365_days) FROM {relation}"
                for relation in ("raw_expected", "staged_expected", "actual")
            ),
        ).fetchall()
        == [(0, 4)] * 3
    )
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM core.fact_order_items WHERE "
        + " OR ".join(column + " IS NULL" for column in COLUMNS)
        + " OR order_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR product_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR seller_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR _source_row<1 OR order_source_row<1 OR order_item_id<1 "
        f"OR price<0 OR price>{MONEY_MAX} OR freight_value<0 OR freight_value>{MONEY_MAX} "
        "OR shipping_calendar_date IS DISTINCT FROM CAST(shipping_limit_date AS date) "
        "OR is_shipping_before_purchase IS DISTINCT FROM "
        "COALESCE(shipping_limit_date<order_purchase_timestamp, false) "
        "OR is_shipping_beyond_365_days IS DISTINCT FROM "
        "COALESCE(shipping_limit_date-order_purchase_timestamp>interval '365 days', false)",
    ).fetchone() == (0,)
    assert _diagnostic(
        connection,
        "WITH item_facts AS MATERIALIZED (SELECT order_id, product_id, seller_id, "
        "shipping_calendar_date FROM core.fact_order_items), "
        "required_dates AS MATERIALIZED (SELECT DISTINCT shipping_calendar_date "
        "FROM item_facts WHERE shipping_calendar_date IS NOT NULL) "
        "SELECT (SELECT count(*) FROM item_facts f WHERE NOT EXISTS ("
        'SELECT 1 FROM core.fact_orders o WHERE f.order_id COLLATE "C"=o.order_id COLLATE "C")), '
        "(SELECT count(*) FROM item_facts f WHERE NOT EXISTS ("
        "SELECT 1 FROM core.dim_product p "
        'WHERE f.product_id COLLATE "C"=p.product_id COLLATE "C")), '
        "(SELECT count(*) FROM item_facts f WHERE NOT EXISTS ("
        'SELECT 1 FROM core.dim_seller s WHERE f.seller_id COLLATE "C"=s.seller_id COLLATE "C")), '
        "(SELECT count(*) FROM required_dates f WHERE NOT EXISTS ("
        "SELECT 1 FROM core.dim_date d WHERE f.shipping_calendar_date=d.calendar_date))",
    ).fetchone() == (0, 0, 0, 0)
