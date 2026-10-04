"""Opt-in native item-fact checks with bounded synthetic read-only inputs.

Render the actual model, four singular checks and installed YAML-configured dbt
null macros. Independent Python Decimal, literal-join and naive datetime oracles
verify complete rows. No source records, fixture tables or warehouse writes occur.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_ITEMS_INTEGRATION") != "1",
    reason="Native read-only item-fact SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
SOURCE_COLUMNS = (
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
FLAG_COLUMNS = ("is_shipping_before_purchase", "is_shipping_beyond_365_days")
COLUMNS = (*SOURCE_COLUMNS, *CONTEXT_COLUMNS, *FLAG_COLUMNS, "shipping_calendar_date")
SOURCE_TYPES = (
    "uuid",
    "bigint",
    "text",
    "bigint",
    "text",
    "text",
    "timestamp without time zone",
    "numeric(18,2)",
    "numeric(18,2)",
)
ORDER_TYPES = ("uuid", "bigint", "text", "timestamp without time zone")
TYPES = (
    *SOURCE_TYPES,
    "timestamp without time zone",
    "uuid",
    "bigint",
    "boolean",
    "boolean",
    "date",
)
TYPE_CODES = (2950, 20, 25, 20, 25, 25, 1114, 1700, 1700, 1114, 2950, 20, 16, 16, 1082)
SINGULAR_COLUMNS = {
    "fact_order_items_grain": ("duplicate_item_key_count",),
    "fact_order_items_domains": ("invalid_item_fact_rows",),
    "fact_order_items_source_reconciliation": (
        "source_item_count",
        "fact_item_count",
        "missing_or_changed_count",
        "extra_or_changed_count",
    ),
    "fact_order_items_relationships": (
        "missing_order_count",
        "missing_product_count",
        "missing_seller_count",
        "missing_shipping_date_count",
    ),
}
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
LOAD_C = UUID("33333333-3333-4333-8333-333333333333")
TARGET_ID = "a" * 32
PRODUCT_ID = "b" * 32
SELLER_ID = "c" * 32
LOWER = datetime(1677, 9, 21, 0, 12, 44)
UPPER = datetime(2262, 4, 11, 23, 47, 16)
ORDERS = (
    (LOAD_B, 4294967297, TARGET_ID, datetime(2018, 1, 1)),
    (LOAD_C, 1, "d" * 32, datetime(2020, 2, 29, 23, 59, 59)),
    (LOAD_A, 1, "e" * 32, LOWER),
    (LOAD_C, 9223372036854775807, "f" * 32, UPPER),
)
ITEMS = (
    (
        LOAD_A,
        4294967297,
        TARGET_ID,
        1,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2018, 1, 1),
        Decimal("9999999999999999.99"),
        Decimal("0.01"),
    ),
    (
        LOAD_A,
        2,
        TARGET_ID,
        2,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2017, 12, 31, 23, 59, 59),
        Decimal("0.00"),
        Decimal("0.00"),
    ),
    (
        LOAD_A,
        3,
        TARGET_ID,
        3,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2019, 1, 1),
        Decimal("0.01"),
        Decimal("9999999999999999.99"),
    ),
    (
        LOAD_A,
        4,
        TARGET_ID,
        4,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2019, 1, 1, 0, 0, 1),
        Decimal("0.10"),
        Decimal("0.10"),
    ),
    (
        LOAD_B,
        1,
        "d" * 32,
        1,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2021, 2, 28, 23, 59, 59),
        Decimal("0.20"),
        Decimal("0.20"),
    ),
    (
        LOAD_B,
        2,
        "d" * 32,
        2,
        PRODUCT_ID,
        SELLER_ID,
        datetime(2021, 3, 1),
        Decimal("123.45"),
        Decimal("4.56"),
    ),
    (
        LOAD_B,
        3,
        "e" * 32,
        9007199254740993,
        PRODUCT_ID,
        SELLER_ID,
        UPPER,
        Decimal("4.56"),
        Decimal("1.23"),
    ),
    (
        LOAD_B,
        4,
        "f" * 32,
        9223372036854775807,
        PRODUCT_ID,
        SELLER_ID,
        LOWER,
        Decimal("20.00"),
        Decimal("123.45"),
    ),
)
DATES = tuple(sorted({row[6].date() for row in ITEMS}))


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_order_items": "synthetic_items",
        "fact_orders": "synthetic_orders",
        "dim_product": "synthetic_products",
        "dim_seller": "synthetic_sellers",
        "dim_date": "synthetic_dates",
        "fact_order_items": "synthetic_projection",
    }[name]


def _render(relative_path: str) -> str:
    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        _environment()
        .from_string((PROJECT / relative_path).read_text("utf-8"))
        .render(ref=_reference, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_sql(column: str) -> str:
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/core/fact_order_items.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert contract["name"] == "fact_order_items"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract["columns"]) == COLUMNS
    assert tuple(item["data_type"] for item in contract["columns"]) == TYPES
    assert all(item["data_tests"] == ["not_null"] for item in contract["columns"])
    assert column in COLUMNS
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql/not_null.sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return module.default__test_not_null(model="synthetic_projection", column_name=column).strip()


def _changed(rows, columns: tuple[str, ...], column: str, replacement: object):
    first = list(rows[0])
    first[columns.index(column)] = replacement
    return (tuple(first), *rows[1:])


def _expected(items=ITEMS, orders=ORDERS) -> Counter:
    expected = []
    for item in items:
        matches = [order for order in orders if item[2] is not None and order[2] == item[2]]
        for order in matches or [None]:
            purchase = order[3] if order is not None else None
            context = (purchase, *order[:2]) if order is not None else (None,) * 3
            shipping = item[6]
            recorded = shipping is not None and purchase is not None
            before = recorded and shipping < purchase
            beyond = recorded and shipping - purchase > timedelta(days=365)
            calendar = shipping.date() if shipping is not None else None
            expected.append((*item, *context, before, beyond, calendar))
    return Counter(expected)


def _cte(
    *,
    items=ITEMS,
    orders=ORDERS,
    products=(PRODUCT_ID,),
    sellers=(SELLER_ID,),
    dates=DATES,
    source_collation: str | None = None,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert source_collation in {None, "C", "POSIX"}
    assert mode in {"same", "missing", "extra", "duplicate", "nulls"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("items", SOURCE_COLUMNS, SOURCE_TYPES, items),
        ("orders", ORDER_COLUMNS, ORDER_TYPES, orders),
        ("products", ("product_id",), ("text",), tuple((v,) for v in products)),
        ("sellers", ("seller_id",), ("text",), tuple((v,) for v in sellers)),
        ("dates", ("calendar_date",), ("date",), tuple((v,) for v in dates)),
    ):
        assert len(rows) <= 8 and all(len(row) == len(columns) for row in rows)
        collate = ' COLLATE "' + source_collation + '"' if source_collation else ""
        casts = [kind + (collate if kind == "text" else "") for kind in types]
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in casts) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in casts) + " where false"
        ctes.append(
            "synthetic_"
            + name
            + " ("
            + ", ".join(columns)
            + ") as materialized ("
            + selection
            + ")"
        )
    ctes.append("synthetic_actual as (" + _render("models/core/fact_order_items.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if mode == "nulls":
            fields.append("null::" + kind + " as " + column)
        elif override is not None and column == override[0]:
            fields.append(
                'case when order_id COLLATE "C"=%s::text COLLATE "C" and order_item_id=1 '
                "then %s::" + kind + " else " + column + " end as " + column
            )
            parameters.extend((TARGET_ID, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += ' where not (order_id COLLATE "C"=%s::text COLLATE "C" and order_item_id=1)'
        parameters.append(TARGET_ID)
    elif mode in {"extra", "duplicate"}:
        added = ["%s::text" if mode == "extra" and c == "order_id" else c for c in COLUMNS]
        selection += " union all select " + ", ".join(added) + " from synthetic_actual "
        selection += 'where order_id COLLATE "C"=%s::text COLLATE "C" and order_item_id=1'
        if mode == "extra":
            parameters.append("9" * 32)
        parameters.append(TARGET_ID)
    ctes.append("synthetic_projection as (" + selection + ")")
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only')"
        ).fetchone() == (
            "commercelens_transformer",
            "on",
        )
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Item-fact native setup failed; inspect private local configuration.", pytrace=False
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    with transformer_connection.transaction():
        yield


def _query(connection: psycopg.Connection, sql: str, **options: object):
    cte, parameters = _cte(**options)
    try:
        return connection.execute(cte + sql, parameters, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Item-fact native diagnostic failed; inspect private local configuration.",
            pytrace=False,
        )


def _singular(connection: psycopg.Connection, name: str, **options: object):
    assert name in SINGULAR_COLUMNS
    sql = _render("tests/" + name + ".sql")
    result = _query(connection, "select * from (" + sql + ") diagnostics", **options)
    assert result.description is not None
    assert tuple(column.name for column in result.description) == SINGULAR_COLUMNS[name]
    return result.fetchall()


def _null_counts(connection: psycopg.Connection, **options: object):
    checks = [
        "(select count(*) from (" + _generic_sql(column) + ") failures)" for column in COLUMNS
    ]
    result = _query(connection, "select " + ", ".join(checks), **options).fetchone()
    return dict(zip(COLUMNS, result, strict=True))


def _assert_shape(result) -> None:
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES
    for position in (7, 8):
        assert (result.description[position].precision, result.description[position].scale) == (
            18,
            2,
        )


@pytest.mark.parametrize("timezone", ["UTC", "Pacific/Honolulu"])
@pytest.mark.parametrize("source_collation", [None, "POSIX"])
def test_actual_model_keeps_exact_money_composite_grain_both_lineages_and_elapsed_clock_flags(
    transformer_connection: psycopg.Connection, timezone: str, source_collation: str | None
) -> None:
    assert timezone in {"UTC", "Pacific/Honolulu"}
    transformer_connection.execute("SET LOCAL TIME ZONE '" + timezone + "'")
    options = {"source_collation": source_collation}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert Counter(result.fetchall()) == _expected()
    assert _query(
        transformer_connection,
        "select count(*), sum(price), sum(freight_value) from synthetic_actual",
        **options,
    ).fetchone() == (
        8,
        sum((row[7] for row in ITEMS), Decimal("0.00")),
        sum((row[8] for row in ITEMS), Decimal("0.00")),
    )
    equalities = " AND ".join(
        f"pg_collation_for(a.{column}) IS NOT DISTINCT FROM pg_collation_for(i.{column})"
        for column in ("order_id", "product_id", "seller_id")
    )
    assert _query(
        transformer_connection,
        "select bool_and(" + equalities + ") from synthetic_actual a join synthetic_items i "
        'on a.order_id COLLATE "C"=i.order_id COLLATE "C" and a.order_item_id=i.order_item_id',
        **options,
    ).fetchone() == (True,)
    for name in SINGULAR_COLUMNS:
        assert _singular(transformer_connection, name, **options) == []
    assert _null_counts(transformer_connection, **options) == dict.fromkeys(COLUMNS, 0)


def test_actual_yaml_all_15_required_fields_block_null_output(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _null_counts(transformer_connection, mode="nulls") == dict.fromkeys(COLUMNS, 8)


@pytest.mark.parametrize("column", ("shipping_limit_date", "order_purchase_timestamp"))
def test_absent_required_clock_keeps_item_and_coalesces_both_warnings_to_false(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    options = (
        {"items": _changed(ITEMS, SOURCE_COLUMNS, column, None)}
        if column == "shipping_limit_date"
        else {"orders": _changed(ORDERS, ORDER_COLUMNS, column, None)}
    )
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == _expected(**options)
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", **options) == []
    )
    counts = _null_counts(transformer_connection, **options)
    assert counts[column] == (1 if column == "shipping_limit_date" else 4)
    assert counts[FLAG_COLUMNS[0]] == counts[FLAG_COLUMNS[1]] == 0


@pytest.mark.parametrize("duplicate_kind", ["identical", "conflicting"])
def test_shared_parent_fanout_fails_independent_source_count_and_composite_grain(
    transformer_connection: psycopg.Connection, duplicate_kind: str
) -> None:
    duplicate = (
        ORDERS[0] if duplicate_kind == "identical" else (LOAD_C, 2, TARGET_ID, datetime(2017, 1, 1))
    )
    orders = (*ORDERS, duplicate)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == _expected(orders=orders)
    assert _singular(
        transformer_connection, "fact_order_items_source_reconciliation", orders=orders
    ) == [(8, 12, 0, 0)]
    assert _singular(transformer_connection, "fact_order_items_grain", orders=orders) == [(4,)]


def test_missing_order_mapping_keeps_all_items_null_context_false_flags_and_blocks_parents(
    transformer_connection: psycopg.Connection,
) -> None:
    orders = ORDERS[1:]
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == _expected(orders=orders)
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", orders=orders)
        == []
    )
    assert _singular(transformer_connection, "fact_order_items_relationships", orders=orders) == [
        (4, 0, 0, 0)
    ]
    counts = _null_counts(transformer_connection, orders=orders)
    assert {column: counts[column] for column in CONTEXT_COLUMNS} == dict.fromkeys(
        CONTEXT_COLUMNS, 4
    )
    assert counts[FLAG_COLUMNS[0]] == counts[FLAG_COLUMNS[1]] == 0


def test_duplicate_source_composite_key_is_retained_and_blocks_grain_without_global_item_id_unique(
    transformer_connection: psycopg.Connection,
) -> None:
    duplicate = (LOAD_C, 1, *ITEMS[0][2:])
    items = (*ITEMS[:2], duplicate)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", items=items).fetchall()
    ) == _expected(items=items)
    assert _singular(transformer_connection, "fact_order_items_grain", items=items) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", items=items)
        == []
    )


MUTATIONS = (
    LOAD_C,
    1,
    "9" * 32,
    2,
    "d" * 32,
    "e" * 32,
    datetime(2018, 1, 2),
    Decimal("0.00"),
    Decimal("0.02"),
    datetime(2017, 1, 1),
    LOAD_C,
    1,
    True,
    True,
    date(2018, 1, 2),
)


@pytest.mark.parametrize("column,replacement", list(zip(COLUMNS, MUTATIONS, strict=True)))
def test_full_15_field_reconciliation_blocks_each_output_mutation_at_constant_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection,
        "fact_order_items_source_reconciliation",
        override=(column, replacement),
    ) == [(8, 8, 1, 1)]


@pytest.mark.parametrize(
    "mode,diagnostics",
    [("missing", (8, 7, 1, 0)), ("extra", (8, 9, 0, 1)), ("duplicate", (8, 9, 0, 1))],
)
def test_full_multiset_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str, diagnostics: tuple[int, ...]
) -> None:
    assert _singular(
        transformer_connection, "fact_order_items_source_reconciliation", mode=mode
    ) == [diagnostics]
    if mode == "duplicate":
        assert _singular(transformer_connection, "fact_order_items_grain", mode=mode) == [(1,)]


@pytest.mark.parametrize("column", ("order_id", "product_id", "seller_id"))
@pytest.mark.parametrize("replacement", ["A" * 32, " " + "a" * 32, "ａ" * 32, "𐍈" * 32])
def test_literal_invalid_ids_are_retained_and_block_domains_without_conversion(
    transformer_connection: psycopg.Connection, column: str, replacement: str
) -> None:
    items = _changed(ITEMS, SOURCE_COLUMNS, column, replacement)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", items=items).fetchall()
    ) == _expected(items=items)
    assert _singular(transformer_connection, "fact_order_items_domains", items=items) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", items=items)
        == []
    )


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("order_item_id", 0),
        ("_source_row", 0),
        ("order_source_row", 0),
        ("price", Decimal("-0.01")),
        ("freight_value", Decimal("-0.01")),
    ],
)
def test_invalid_typed_amounts_and_ordinals_remain_visible_and_fail_domains(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    options = (
        {"orders": _changed(ORDERS, ORDER_COLUMNS, "_source_row", replacement)}
        if column == "order_source_row"
        else {"items": _changed(ITEMS, SOURCE_COLUMNS, column, replacement)}
    )
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == _expected(**options)
    assert _singular(transformer_connection, "fact_order_items_domains", **options) == [
        (4 if column == "order_source_row" else 1,)
    ]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", **options) == []
    )


@pytest.mark.parametrize("column", ("price", "freight_value"))
def test_numeric_nan_is_retained_for_blocking_domain_validation(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    items = _changed(ITEMS, SOURCE_COLUMNS, column, Decimal("NaN"))
    actual = _query(
        transformer_connection,
        "select "
        + column
        + " from synthetic_actual where order_item_id=1 and _source_row=4294967297",
        items=items,
    ).fetchone()[0]
    assert type(actual) is Decimal and actual.is_nan()
    assert _singular(transformer_connection, "fact_order_items_domains", items=items) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", items=items)
        == []
    )


@pytest.mark.parametrize("column", FLAG_COLUMNS)
@pytest.mark.parametrize("replacement", [None, True])
def test_each_exact_warning_flag_mismatch_blocks_domains_and_reconciliation(
    transformer_connection: psycopg.Connection, column: str, replacement: bool | None
) -> None:
    options = {"override": (column, replacement)}
    assert _singular(transformer_connection, "fact_order_items_domains", **options) == [(1,)]
    assert _singular(
        transformer_connection, "fact_order_items_source_reconciliation", **options
    ) == [(8, 8, 1, 1)]


@pytest.mark.parametrize("replacement", [None, date(2030, 1, 1)])
def test_direct_calendar_date_mismatch_blocks_domains_and_nonnull_missing_parent(
    transformer_connection: psycopg.Connection, replacement: date | None
) -> None:
    options = {"override": ("shipping_calendar_date", replacement)}
    assert _singular(transformer_connection, "fact_order_items_domains", **options) == [(1,)]
    assert _singular(
        transformer_connection, "fact_order_items_source_reconciliation", **options
    ) == [(8, 8, 1, 1)]
    assert _singular(transformer_connection, "fact_order_items_relationships", **options) == (
        [] if replacement is None else [(0, 0, 0, 1)]
    )


@pytest.mark.parametrize("parent", ["product", "seller", "date"])
def test_required_literal_dimension_parent_missing_blocks_without_item_filter(
    transformer_connection: psycopg.Connection, parent: str
) -> None:
    options = (
        {"products": ()}
        if parent == "product"
        else {"sellers": ()}
        if parent == "seller"
        else {"dates": DATES[1:]}
    )
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        )
        == _expected()
    )
    assert _singular(transformer_connection, "fact_order_items_relationships", **options) == [
        (0, 8, 0, 0)
        if parent == "product"
        else (0, 0, 8, 0)
        if parent == "seller"
        else (0, 0, 0, 1)
    ]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", **options) == []
    )


@pytest.mark.parametrize("parent", ["order", "product", "seller"])
@pytest.mark.parametrize("variation", ["case", "whitespace", "unicode"])
def test_parent_reference_lookup_is_literal_for_case_whitespace_and_unicode(
    transformer_connection: psycopg.Connection, parent: str, variation: str
) -> None:
    identifier = {"order": TARGET_ID, "product": PRODUCT_ID, "seller": SELLER_ID}[parent]
    literal = (
        identifier.upper()
        if variation == "case"
        else " " + identifier + " "
        if variation == "whitespace"
        else chr(ord(identifier[0]) + 0xFEE0) * 32
    )
    options = (
        {"orders": _changed(ORDERS, ORDER_COLUMNS, "order_id", literal)}
        if parent == "order"
        else {"products": (literal,)}
        if parent == "product"
        else {"sellers": (literal,)}
    )
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == _expected(orders=options.get("orders", ORDERS))
    assert _singular(transformer_connection, "fact_order_items_relationships", **options)


def test_repeated_dimension_keys_cannot_multiply_items_or_change_shipping_context(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {
        "products": (PRODUCT_ID,) * 2,
        "sellers": (SELLER_ID,) * 2,
        "dates": (*DATES, DATES[0]),
    }
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        )
        == _expected()
    )
    for name in SINGULAR_COLUMNS:
        assert _singular(transformer_connection, name, **options) == []


def test_empty_source_has_15_typed_fields_exact_money_typmods_and_zero_failures(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {"items": (), "orders": (), "products": (), "sellers": (), "dates": ()}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert result.fetchall() == []
    for name in SINGULAR_COLUMNS:
        assert _singular(transformer_connection, name, **options) == []
    assert _null_counts(transformer_connection, **options) == dict.fromkeys(COLUMNS, 0)


def test_all_null_source_is_retained_with_typed_false_flags_and_blocked_required_fields(
    transformer_connection: psycopg.Connection,
) -> None:
    items = ((None,) * len(SOURCE_COLUMNS),)
    result = _query(transformer_connection, "select * from synthetic_actual", items=items)
    _assert_shape(result)
    assert result.fetchall() == [(None,) * 12 + (False, False, None)]
    assert (
        _singular(transformer_connection, "fact_order_items_source_reconciliation", items=items)
        == []
    )
    assert _singular(transformer_connection, "fact_order_items_domains", items=items) == [(1,)]
    assert _singular(transformer_connection, "fact_order_items_relationships", items=items) == [
        (1, 1, 1, 0)
    ]
    assert _null_counts(transformer_connection, items=items) == {
        column: 0 if column in FLAG_COLUMNS else 1 for column in COLUMNS
    }
