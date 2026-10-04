"""Execute actual item-fact model/tests with query-only synthetic SQLite CTEs.

Configured generics render installed dbt macros. Whole-second datetime subtraction,
date casting, regex and occurrence-aware EXCEPT ALL have bounded SQLite adapters.
Money uses zero, binary-exact small examples and a safely representable value near
the upper limit; SQLite cannot prove exact .99 cents, scale or numeric(18,2) limits.
Native PostgreSQL remains authoritative for exact money, types and timestamps.
No private configuration, network, datasets or persistent fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = "11111111-1111-4111-8111-111111111111"
OTHER_LOAD = "22222222-2222-4222-8222-222222222222"
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
CONTEXT = ("order_purchase_timestamp", "order_load_id", "order_source_row")
FLAGS = ("is_shipping_before_purchase", "is_shipping_beyond_365_days")
COLUMNS = (*SOURCE_COLUMNS, *CONTEXT, *FLAGS, "shipping_calendar_date")
ORDER_COLUMNS = ("_load_id", "_source_row", "order_id", "order_purchase_timestamp")
NEAR_MAX_MONEY = 9_999_999_999_999_998.0
ITEMS = (
    (LOAD, 1, "a" * 32, 1, "c" * 32, "d" * 32, "2018-01-10 01:02:02", 0.0, 0.0),
    (LOAD, 2, "a" * 32, 2, "c" * 32, "e" * 32, "2019-01-10 01:02:03", 12.5, NEAR_MAX_MONEY),
    (OTHER_LOAD, 1, "b" * 32, 1, "f" * 32, "d" * 32, "2021-02-28 23:59:59", NEAR_MAX_MONEY, 2.25),
)
ORDERS = (
    (OTHER_LOAD, 100, "a" * 32, "2018-01-10 01:02:03"),
    (LOAD, 200, "b" * 32, "2020-02-28 23:59:59"),
)
PRODUCTS = (("c" * 32,), ("f" * 32,))
SELLERS = (("d" * 32,), ("e" * 32,))
DATES = (("2018-01-10",), ("2019-01-10",), ("2021-02-28",))
EXPECTED = (
    (*ITEMS[0], "2018-01-10 01:02:03", OTHER_LOAD, 100, True, False, "2018-01-10"),
    (*ITEMS[1], "2018-01-10 01:02:03", OTHER_LOAD, 100, False, False, "2019-01-10"),
    (*ITEMS[2], "2020-02-28 23:59:59", LOAD, 200, False, True, "2021-02-28"),
)
SUBSTITUTIONS = {
    "_load_id": "'33333333-3333-4333-8333-333333333333'",
    "_source_row": "_source_row + 1",
    "order_id": "'cccccccccccccccccccccccccccccccc'",
    "order_item_id": "order_item_id + 1",
    "product_id": "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'",
    "seller_id": "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'",
    "shipping_limit_date": "'2001-01-01 01:02:03'",
    "price": "0.25",
    "freight_value": "0.5",
    "order_purchase_timestamp": "'2001-01-01 01:02:03'",
    "order_load_id": "'33333333-3333-4333-8333-333333333333'",
    "order_source_row": "order_source_row + 1",
    **{column: "not " + column for column in FLAGS},
    "shipping_calendar_date": "'2001-01-01'",
}
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join("99" if column == "order_item_id" else column for column in COLUMNS)
    + " from projected where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' and order_item_id = 1"
)


def render(relative: str) -> str:
    jinja = pytest.importorskip("jinja2")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        ref=lambda name: name,
        config=config,
    )


def contract() -> dict:
    return pytest.importorskip("yaml").safe_load(
        (PROJECT / "models/core/fact_order_items.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
    definition = next(
        test
        for test in tests
        if test == "not_null" or isinstance(test, dict) and "not_null" in test
    )
    arguments = dict(definition["not_null"]["arguments"]) if isinstance(definition, dict) else {}
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql/not_null.sql"
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return module.default__test_not_null(model="fact_order_items", column_name=column, **arguments)


def elapsed_seconds(shipping: str | None, purchase: str | None) -> int | None:
    """Adapt timestamp-minus-timestamp at the source's whole-second resolution."""
    if shipping is None or purchase is None:
        return None
    difference = datetime.fromisoformat(shipping) - datetime.fromisoformat(purchase)
    return difference.days * 86_400 + difference.seconds


def sqlite_statement(statement: str) -> str:
    statement = re.sub(
        r"((?:i\.)?shipping_limit_date)\s*-\s*((?:o\.)?order_purchase_timestamp)"
        r"\s*>\s*interval\s*'365 days'",
        lambda match: f"elapsed_seconds({match[1]}, {match[2]}) > 31536000",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(
        r"cast\(((?:i\.)?shipping_limit_date) as date\)",
        lambda match: "date(" + match[1] + ")",
        statement,
        flags=re.IGNORECASE,
    ).replace(" !~ ", " not regexp ")

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        fields = ", ".join(COLUMNS)
        matches = " and ".join(f"l.{column} is r.{column}" for column in COLUMNS)
        return (
            "select "
            + ", ".join("l." + column for column in COLUMNS)
            + f" from (select *, row_number() over (partition by {fields})"
            + f" as occurrence from {left}) l"
            + f" left join (select *, row_number() over (partition by {fields})"
            + f" as occurrence from {right}) r"
            + f" on {matches} and l.occurrence = r.occurrence where r.occurrence is null"
        )

    return re.sub(
        r"select \* from (expected|actual)\s+except all\s+select \* from (expected|actual)",
        subtract,
        statement,
        flags=re.IGNORECASE,
    )


def run_sql(
    singular: str | None = None,
    generic: str | None = None,
    *,
    items: tuple[tuple[object, ...], ...] = ITEMS,
    orders: tuple[tuple[object, ...], ...] = ORDERS,
    products: tuple[tuple[object, ...], ...] = PRODUCTS,
    sellers: tuple[tuple[object, ...], ...] = SELLERS,
    dates: tuple[tuple[object, ...], ...] = DATES,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_order_items", SOURCE_COLUMNS, items),
        ("fact_orders", ORDER_COLUMNS, orders),
        ("dim_product", ("product_id",), products),
        ("dim_seller", ("seller_id",), sellers),
        ("dim_date", ("calendar_date",), dates),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/fact_order_items.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"fact_order_items as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(generic)
        if generic
        else "select * from fact_order_items"
    )
    statement = sqlite_statement(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    )
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
        connection.create_function("elapsed_seconds", 2, elapsed_seconds)
        connection.create_function(
            "regexp",
            2,
            lambda pattern, value: (
                None if value is None else int(re.fullmatch(pattern, value) is not None)
            ),
        )
        connection.execute("pragma query_only=on")
        result = connection.execute(statement, values)
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()


def test_composite_item_grain_preserves_source_money_context_lineage_and_warning_flags() -> None:
    assert sorted(run_sql(), key=lambda row: row[2:4]) == list(EXPECTED)
    for singular in (
        "fact_order_items_grain",
        "fact_order_items_domains",
        "fact_order_items_source_reconciliation",
        "fact_order_items_relationships",
    ):
        assert run_sql(singular) == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
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
    ]
    for column in COLUMNS:
        assert run_sql(generic=column) == []
    assert sum(len(item["data_tests"]) for item in contract()["columns"]) == 15


@pytest.mark.parametrize("column", COLUMNS)
def test_each_required_null_output_fails_the_installed_yaml_generic(column: str) -> None:
    assert run_sql(generic=column, changes={column: "null"})
    assert run_sql("fact_order_items_source_reconciliation", changes={column: "null"})


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_every_source_context_flag_or_date_field_change_fails_full_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("fact_order_items_source_reconciliation", changes={column: expression})


@pytest.mark.parametrize(
    "purchase,shipping,before,beyond,calendar_date",
    [
        ("2018-01-01 00:00:01", "2018-01-01 00:00:00", True, False, "2018-01-01"),
        ("2018-01-01 00:00:00", "2018-01-01 00:00:00", False, False, "2018-01-01"),
        ("2018-01-01 00:00:00", "2018-12-31 23:59:59", False, False, "2018-12-31"),
        ("2018-01-01 00:00:00", "2019-01-01 00:00:00", False, False, "2019-01-01"),
        ("2018-01-01 00:00:00", "2019-01-01 00:00:01", False, True, "2019-01-01"),
        ("2020-02-28 00:00:00", "2021-02-27 00:00:00", False, False, "2021-02-27"),
        ("2020-02-28 00:00:00", "2021-02-28 00:00:00", False, True, "2021-02-28"),
        ("1677-09-21 00:12:44", "2262-04-11 23:47:16", False, True, "2262-04-11"),
        ("2262-04-11 23:47:16", "1677-09-21 00:12:44", True, False, "1677-09-21"),
    ],
)
def test_shipping_thresholds_use_exact_elapsed_days_and_seconds_without_filtering(
    purchase: str, shipping: str, before: bool, beyond: bool, calendar_date: str
) -> None:
    item = (*ITEMS[0][:6], shipping, 0.0, 0.0)
    inputs = {
        "items": (item,),
        "orders": ((OTHER_LOAD, 100, "a" * 32, purchase),),
        "dates": ((calendar_date,),),
    }
    assert run_sql(**inputs) == [(*item, purchase, OTHER_LOAD, 100, before, beyond, calendar_date)]
    assert run_sql("fact_order_items_domains", **inputs) == []
    assert run_sql("fact_order_items_source_reconciliation", **inputs) == []


def test_missing_parent_order_retains_items_with_false_flags_and_blocks_required_context() -> None:
    orders = ORDERS[1:]
    result = sorted(run_sql(orders=orders), key=lambda row: row[2:4])
    assert result[:2] == [
        (*ITEMS[0], None, None, None, False, False, "2018-01-10"),
        (*ITEMS[1], None, None, None, False, False, "2019-01-10"),
    ]
    assert len(result) == len(ITEMS)
    for column in CONTEXT:
        assert run_sql(generic=column, orders=orders) == [(None,), (None,)]
    assert run_sql("fact_order_items_relationships", orders=orders) == [(2, 0, 0, 0)]
    assert run_sql("fact_order_items_source_reconciliation", orders=orders) == []


@pytest.mark.parametrize("missing", ["shipping", "purchase"])
def test_absent_clock_returns_false_flags_and_blocks_its_required_value(missing: str) -> None:
    shipping = None if missing == "shipping" else ITEMS[0][6]
    purchase = None if missing == "purchase" else ORDERS[0][3]
    inputs = {
        "items": ((*ITEMS[0][:6], shipping, *ITEMS[0][7:]),),
        "orders": ((*ORDERS[0][:3], purchase),),
    }
    result = run_sql(**inputs)
    assert result[0][12:14] == (False, False)
    required = "shipping_limit_date" if missing == "shipping" else "order_purchase_timestamp"
    assert run_sql(generic=required, **inputs) == [(None,)]
    assert run_sql("fact_order_items_source_reconciliation", **inputs) == []


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_order_context_fanout_blocks_grain_and_independent_source_count(
    conflicting: bool,
) -> None:
    duplicate = (*ORDERS[0][:3], "2017-01-01 00:00:00") if conflicting else ORDERS[0]
    orders = (*ORDERS, duplicate)
    assert len(run_sql(orders=orders)) == 5
    assert run_sql("fact_order_items_grain", orders=orders) == [(2,)]
    assert run_sql("fact_order_items_source_reconciliation", orders=orders) == [(3, 5, 0, 0)]


@pytest.mark.parametrize(
    "parents,expected",
    [
        ({"products": PRODUCTS[1:]}, (0, 2, 0, 0)),
        ({"sellers": SELLERS[1:]}, (0, 0, 2, 0)),
        ({"dates": DATES[1:]}, (0, 0, 0, 1)),
    ],
)
def test_missing_product_seller_or_shipping_date_blocks_without_filtering_source_items(
    parents: dict, expected: tuple[int, int, int, int]
) -> None:
    assert sorted(run_sql(**parents), key=lambda row: row[2:4]) == list(EXPECTED)
    assert run_sql("fact_order_items_relationships", **parents) == [expected]


@pytest.mark.parametrize(
    "parents,expected",
    [
        ({"orders": ((*ORDERS[0][:2], "A" * 32, ORDERS[0][3]), ORDERS[1])}, (2, 0, 0, 0)),
        ({"products": (("C" * 32,), PRODUCTS[1])}, (0, 2, 0, 0)),
        ({"sellers": (("D" * 32,), SELLERS[1])}, (0, 0, 2, 0)),
    ],
)
def test_order_join_and_reference_membership_use_literal_c_collation(
    parents: dict, expected: tuple[int, int, int, int]
) -> None:
    assert len(run_sql(**parents)) == len(ITEMS)
    assert run_sql("fact_order_items_relationships", **parents) == [expected]


def test_product_seller_dimension_duplicates_cannot_fan_out_the_fact_projection() -> None:
    parents = {"products": (*PRODUCTS, PRODUCTS[0]), "sellers": (*SELLERS, SELLERS[0])}
    assert sorted(run_sql(**parents), key=lambda row: row[2:4]) == list(EXPECTED)
    assert run_sql("fact_order_items_source_reconciliation", **parents) == []


@pytest.mark.parametrize("column", ["order_id", "product_id", "seller_id"])
@pytest.mark.parametrize(
    "expression",
    [
        "'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'",
        "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
        "'１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１'",
    ],
)
def test_literal_ascii_lowercase_key_domains_reject_invalid_output(
    column: str, expression: str
) -> None:
    assert run_sql("fact_order_items_domains", changes={column: expression})


@pytest.mark.parametrize("column", ["_source_row", "order_source_row", "order_item_id"])
@pytest.mark.parametrize("expression", ["0", "-1"])
def test_source_parent_and_item_ordinals_must_be_positive(column: str, expression: str) -> None:
    assert run_sql("fact_order_items_domains", changes={column: expression})


@pytest.mark.parametrize("column", ["price", "freight_value"])
@pytest.mark.parametrize("expression", ["-0.25", "1e17"])
def test_money_domains_block_negative_and_clearly_out_of_range_values(
    column: str, expression: str
) -> None:
    assert run_sql("fact_order_items_domains", changes={column: expression})


@pytest.mark.parametrize("column", FLAGS)
def test_chronology_flags_must_match_retained_clocks(column: str) -> None:
    assert run_sql("fact_order_items_domains", changes={column: "not " + column}) == [(3,)]


def test_spurious_calendar_key_for_missing_shipping_clock_fails_null_safe_correspondence() -> None:
    item = (*ITEMS[0][:6], None, *ITEMS[0][7:])
    assert run_sql(
        "fact_order_items_domains",
        items=(item,),
        changes={"shipping_calendar_date": "'2018-01-10'"},
    ) == [(1,)]


@pytest.mark.parametrize(
    "corruption,expected",
    [
        (
            {
                "predicate": "not (order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "
                "and order_item_id = 1)"
            },
            (3, 2, 1, 0),
        ),
        ({"suffix": EXTRA_OUTPUT}, (3, 4, 0, 1)),
        (
            {
                "suffix": " union all select * from projected "
                "where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' and order_item_id = 1"
            },
            (3, 4, 0, 1),
        ),
    ],
)
def test_omitted_warning_item_extra_or_duplicate_output_fails_conservation(
    corruption: dict, expected: tuple[int, int, int, int]
) -> None:
    assert run_sql("fact_order_items_source_reconciliation", **corruption) == [expected]


def test_duplicate_source_composite_key_is_retained_and_blocks_grain() -> None:
    items = (*ITEMS, ITEMS[0])
    assert len(run_sql(items=items)) == 4
    assert run_sql("fact_order_items_grain", items=items) == [(1,)]
    assert run_sql("fact_order_items_source_reconciliation", items=items) == []


def test_empty_input_relations_produce_empty_valid_item_fact() -> None:
    inputs = {"items": (), "orders": (), "products": (), "sellers": (), "dates": ()}
    assert run_sql(**inputs) == []
    for singular in (
        "fact_order_items_grain",
        "fact_order_items_domains",
        "fact_order_items_source_reconciliation",
        "fact_order_items_relationships",
    ):
        assert run_sql(singular, **inputs) == []
    for column in COLUMNS:
        assert run_sql(generic=column, **inputs) == []
