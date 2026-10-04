"""Execute actual technical-mart SQL with bounded query-only SQLite fixtures.

An independent Python per-order oracle reads accepted component values, without
reusing production code or the model's aggregate-then-join construction. Installed
dbt macros render the YAML-configured not_null test. Regex, PostgreSQL type suffixes
and occurrence-aware EXCEPT ALL use bounded SQLite adapters. Small binary-exact
money fixtures cannot prove native cents, typmods, numeric aggregate headroom,
physical types or native multiset semantics; native PostgreSQL owns those checks.
No raw parsing, private configuration, network, datasets or fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = "11111111-1111-4111-8111-111111111111"
OTHER_LOAD = "22222222-2222-4222-8222-222222222222"
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
COLUMNS = (*ORDER_COLUMNS, *COMPONENT_COLUMNS)
CHILD_COMPARISON_COLUMNS = (
    "order_id",
    "component",
    "component_count",
    "amount_a",
    "amount_b",
    "warning_a",
    "warning_b",
    "warning_c",
)
ITEM_COLUMNS = (
    "order_id",
    "order_item_id",
    "price",
    "freight_value",
    "is_shipping_before_purchase",
    "is_shipping_beyond_365_days",
)
PAYMENT_COLUMNS = (
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
    "is_zero_installments",
    "is_zero_payment_value",
    "is_undefined_payment_type",
)
REVIEW_COLUMNS = ("review_id", "order_id", "is_answer_before_creation")
ORDER_NORMAL = (
    LOAD,
    10,
    "a" * 32,
    "1" * 32,
    "delivered",
    "2018-01-10 23:59:59",
    "2018-01-11 00:00:00",
    "2018-01-12 04:05:06",
    "2018-01-13 12:34:56",
    "2018-01-14 00:00:00",
    *([False] * 12),
    "e" * 32,
    "00123",
    " São Paulo🙂 ",
    "SP",
    OTHER_LOAD,
    100,
    "2018-01-10",
    "2018-01-11",
    "2018-01-12",
    "2018-01-13",
    "2018-01-14",
)
ORDERS = (
    ORDER_NORMAL,
    (
        OTHER_LOAD,
        1,
        "b" * 32,
        "2" * 32,
        "canceled",
        "2018-02-28 23:59:59",
        None,
        None,
        None,
        "2018-03-10 00:00:00",
        True,
        True,
        True,
        *([False] * 9),
        "e" * 32,
        "7",
        " MIXED Case ",
        "RJ",
        LOAD,
        200,
        "2018-02-28",
        None,
        None,
        None,
        "2018-03-10",
    ),
    (
        LOAD,
        11,
        "c" * 32,
        "3" * 32,
        "unavailable",
        "2020-04-09 23:59:59",
        "2020-04-08 03:04:05",
        "2020-04-07 02:03:04",
        "2020-04-06 01:02:03",
        "2020-04-10 00:00:00",
        *([False] * 6),
        *([True] * 6),
        "f" * 32,
        "2",
        " ",
        "AM",
        OTHER_LOAD,
        101,
        "2020-04-09",
        "2020-04-08",
        "2020-04-07",
        "2020-04-06",
        "2020-04-10",
    ),
    (LOAD, 13, "d" * 32, ORDER_NORMAL[3], "shipped", *ORDER_NORMAL[5:]),
    (LOAD, 14, "e" * 32, ORDER_NORMAL[3], "processing", *ORDER_NORMAL[5:]),
)
ITEMS = (
    ("a" * 32, 1, 3.5, 0.5, True, False),
    ("a" * 32, 2, 2.25, 0.25, False, True),
    ("b" * 32, 1, 0.0, 0.0, False, False),
)
PAYMENTS = (
    ("a" * 32, 1, "not_defined", 0, 0.0, True, True, True),
    ("a" * 32, 2, "voucher", 1, 0.5, False, False, False),
    ("a" * 32, 3, "credit_card", 0, 1.25, True, False, False),
    ("b" * 32, 1, "boleto", 1, 0.0, False, True, False),
    ("e" * 32, 1, "debit_card", 2, 2.0, False, False, False),
)
REVIEWS = (
    ("1" * 32, "a" * 32, False),
    ("2" * 32, "a" * 32, True),
    ("1" * 32, "b" * 32, False),
    ("3" * 32, "d" * 32, False),
)
SINGULARS = (
    "order_components_grain",
    "order_components_domains",
    "order_components_orders_reconciliation",
    "order_components_children_reconciliation",
)
PARENT_CHANGES = {
    "_load_id": "'33333333-3333-4333-8333-333333333333'",
    "_source_row": "_source_row + 1",
    "order_id": "'99999999999999999999999999999999'",
    "customer_id": "'44444444444444444444444444444444'",
    "order_status": "'created'",
    **{column: "'2001-01-01 01:02:03'" for column in ORDER_COLUMNS[5:10]},
    **{column: "not " + column for column in ORDER_COLUMNS[10:22]},
    "customer_unique_id": "'99999999999999999999999999999999'",
    "customer_zip_code_prefix": "'00124'",
    "customer_city": "customer_city || ' changed'",
    "customer_state": "'MG'",
    "customer_load_id": "'33333333-3333-4333-8333-333333333333'",
    "customer_source_row": "customer_source_row + 1",
    **{column: "'2001-01-01'" for column in ORDER_COLUMNS[28:]},
}
COMPONENT_CHANGES = {
    column: "not " + column
    if column.startswith("has_")
    else "coalesce(" + column + ", 0) + 0.25"
    if column.endswith("_sum")
    else column + " + 1"
    for column in COMPONENT_COLUMNS
}
DUPLICATE_OUTPUT = (
    " union all select * from model_output where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
)
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join("'99999999999999999999999999999999'" if c == "order_id" else c for c in COLUMNS)
    + " from model_output where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
)


def expected_rows(orders=ORDERS, items=ITEMS, payments=PAYMENTS, reviews=REVIEWS) -> list[tuple]:
    """Independent fixture oracle scans each child list for each literal parent."""
    rows = []
    for order in orders:
        key = order[2]
        item = [row for row in items if row[0] == key]
        payment = [row for row in payments if row[0] == key]
        review = [row for row in reviews if row[1] == key]
        rows.append(
            (
                *order,
                len(item),
                sum(row[2] for row in item) if item else None,
                sum(row[3] for row in item) if item else None,
                sum(row[4] for row in item),
                sum(row[5] for row in item),
                bool(item),
                len(payment),
                sum(row[4] for row in payment) if payment else None,
                sum(row[5] for row in payment),
                sum(row[6] for row in payment),
                sum(row[7] for row in payment),
                bool(payment),
                len(review),
                sum(row[2] for row in review),
                bool(review),
                len(review) > 1,
            )
        )
    return rows


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
        (PROJECT / "models/marts/mart_order_components.yml").read_text("utf-8")
    )["models"][0]


def generic_sql() -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == "order_id")
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
    return module.default__test_not_null(
        model="mart_order_components", column_name="order_id", **arguments
    )


def sqlite_statement(statement: str, comparison_columns: tuple[str, ...]) -> str:
    statement = re.sub(r"::(?:text|numeric|bigint)\b", "", statement, flags=re.IGNORECASE)
    statement = statement.replace(" !~ ", " not regexp ")

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        fields = ", ".join(comparison_columns)
        matches = " and ".join(f"l.{column} is r.{column}" for column in comparison_columns)
        return (
            "select "
            + ", ".join("l." + column for column in comparison_columns)
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
    *,
    generic: bool = False,
    orders=ORDERS,
    items=ITEMS,
    payments=PAYMENTS,
    reviews=REVIEWS,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("fact_orders", ORDER_COLUMNS, orders),
        ("fact_order_items", ITEM_COLUMNS, items),
        ("fact_payments", PAYMENT_COLUMNS, payments),
        ("fact_reviews", REVIEW_COLUMNS, reviews),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("model_output as (" + render("models/marts/mart_order_components.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(
        f"mart_order_components as (select {fields} from model_output where {predicate}{suffix})"
    )
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql()
        if generic
        else "select * from mart_order_components"
    )
    comparison_columns = (
        CHILD_COMPARISON_COLUMNS
        if singular == "order_components_children_reconciliation"
        else ORDER_COLUMNS
    )
    statement = sqlite_statement(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result", comparison_columns
    )
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
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


def test_independent_children_do_not_multiply_money_and_preserve_every_parent_field() -> None:
    rows = run_sql()
    assert Counter(rows) == Counter(expected_rows())
    assert Counter(row[:33] for row in rows) == Counter(ORDERS)
    components = {row[2]: row[33:] for row in rows}
    assert components["a" * 32] == (
        2,
        5.75,
        0.75,
        1,
        1,
        True,
        3,
        1.75,
        2,
        1,
        1,
        True,
        2,
        1,
        True,
        True,
    )
    assert components["b" * 32] == (
        1,
        0.0,
        0.0,
        0,
        0,
        True,
        1,
        0.0,
        0,
        1,
        0,
        True,
        1,
        0,
        True,
        False,
    )
    assert components["c" * 32] == (
        0,
        None,
        None,
        0,
        0,
        False,
        0,
        None,
        0,
        0,
        0,
        False,
        0,
        0,
        False,
        False,
    )
    for singular in SINGULARS:
        assert run_sql(singular) == []
    assert run_sql(generic=True) == []
    assert contract()["config"] == {"materialized": "view", "schema": "marts"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
        "uuid",
        "bigint",
        *(["text"] * 3),
        *(["timestamp without time zone"] * 5),
        *(["boolean"] * 12),
        *(["text"] * 4),
        "uuid",
        "bigint",
        *(["date"] * 5),
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
    ]
    assert sum(len(item.get("data_tests", [])) for item in contract()["columns"]) == 1


@pytest.mark.parametrize("column,expression", PARENT_CHANGES.items())
def test_each_of_33_parent_field_changes_fails_complete_parent_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("order_components_orders_reconciliation", changes={column: expression}) == [
        (5, 5)
    ]


@pytest.mark.parametrize("column,expression", COMPONENT_CHANGES.items())
def test_component_count_amount_warning_and_presence_corruption_blocks_acceptance(
    column: str, expression: str
) -> None:
    changes = {column: expression}
    assert run_sql("order_components_domains", changes=changes)
    if column != "has_multiple_reviews":
        assert run_sql("order_components_children_reconciliation", changes=changes)


@pytest.mark.parametrize(
    "column",
    [
        "item_count",
        "payment_count",
        "review_count",
        "has_items",
        "has_payments",
        "has_reviews",
        "has_multiple_reviews",
        "source_price_sum",
        "source_freight_sum",
        "source_payment_sum",
    ],
)
def test_null_required_or_present_component_output_blocks_null_safe_domains(column: str) -> None:
    assert run_sql("order_components_domains", changes={column: "null"})


def test_null_order_key_fails_installed_yaml_generic_domains_and_parent_conservation() -> None:
    changes = {"order_id": "null"}
    assert run_sql(generic=True, changes=changes) == [(None,)] * 5
    assert run_sql("order_components_domains", changes=changes) == [(5,)]
    assert run_sql("order_components_orders_reconciliation", changes=changes) == [(5, 5)]


@pytest.mark.parametrize("all_empty", [False, True])
def test_empty_children_or_all_empty_relations_preserve_absence_semantics(all_empty: bool) -> None:
    inputs = {"orders": () if all_empty else ORDERS, "items": (), "payments": (), "reviews": ()}
    assert Counter(run_sql(**inputs)) == Counter(expected_rows(**inputs))
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []
    assert run_sql(generic=True, **inputs) == []


def test_missing_all_parent_orders_retains_empty_mart_and_blocks_orphan_child_components() -> None:
    assert run_sql(orders=()) == []
    assert run_sql("order_components_orders_reconciliation", orders=()) == []
    assert run_sql("order_components_children_reconciliation", orders=()) == [(8, 0)]


@pytest.mark.parametrize(
    "status",
    [
        "created",
        "approved",
        "invoiced",
        "processing",
        "shipped",
        "delivered",
        "unavailable",
        "canceled",
    ],
)
def test_every_accepted_order_status_is_retained_with_all_components(status: str) -> None:
    order = (*ORDER_NORMAL[:4], status, *ORDER_NORMAL[5:])
    inputs = {
        "orders": (order,),
        "items": ITEMS[:2],
        "payments": PAYMENTS[:3],
        "reviews": REVIEWS[:2],
    }
    assert Counter(run_sql(**inputs)) == Counter(expected_rows(**inputs))
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []


@pytest.mark.parametrize("relation", ["items", "payments", "reviews"])
def test_literal_child_key_mismatch_cannot_attach_to_another_parent(relation: str) -> None:
    rows = {"items": ITEMS, "payments": PAYMENTS, "reviews": REVIEWS}[relation]
    position = 1 if relation == "reviews" else 0
    row = list(rows[0])
    row[position] = "A" * 32
    inputs = {relation: (tuple(row), *rows[1:])}
    assert Counter(run_sql(**inputs)) == Counter(expected_rows(**inputs))
    assert run_sql("order_components_children_reconciliation", **inputs) == [(1, 0)]


@pytest.mark.parametrize(
    "column,first,second,additional",
    [
        ("source_price_sum", "0", "5.75", {}),
        ("source_payment_sum", "0", "1.75", {}),
        (
            "review_count",
            "1",
            "2",
            {"has_multiple_reviews": "order_id = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'"},
        ),
        ("shipping_before_purchase_count", "0", "1", {}),
        ("zero_installments_count", "1", "1", {}),
    ],
)
def test_per_order_redistribution_fails_even_when_global_totals_and_domains_match(
    column: str, first: str, second: str, additional: dict
) -> None:
    expression = (
        "case when order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' then "
        + first
        + " when order_id = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' then "
        + second
        + " else "
        + column
        + " end"
    )
    changes = {column: expression, **additional}
    index = COLUMNS.index(column)
    assert sum(row[index] or 0 for row in run_sql(changes=changes)) == sum(
        row[index] or 0 for row in expected_rows()
    )
    assert run_sql("order_components_domains", changes=changes) == []
    assert run_sql("order_components_orders_reconciliation", changes=changes) == []
    assert run_sql("order_components_children_reconciliation", changes=changes) == [(2, 2)]


@pytest.mark.parametrize(
    "corruption,diagnostics,duplicate",
    [
        ({"predicate": "order_id <> 'cccccccccccccccccccccccccccccccc'"}, (1, 0), False),
        ({"suffix": EXTRA_OUTPUT}, (0, 1), False),
        ({"suffix": DUPLICATE_OUTPUT}, (0, 1), True),
    ],
)
def test_missing_absent_child_order_extra_or_duplicate_output_fails_parent_multiset(
    corruption: dict, diagnostics: tuple, duplicate: bool
) -> None:
    assert run_sql("order_components_orders_reconciliation", **corruption) == [diagnostics]
    assert bool(run_sql("order_components_grain", **corruption)) == duplicate


def test_count_preserving_duplicate_replacement_fails_both_parent_multiset_directions() -> None:
    corruption = {
        "predicate": "order_id <> 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'",
        "suffix": DUPLICATE_OUTPUT,
    }
    assert len(run_sql(**corruption)) == len(ORDERS)
    assert run_sql("order_components_orders_reconciliation", **corruption) == [(1, 1)]
    assert run_sql("order_components_grain", **corruption) == [(1,)]
    assert run_sql("order_components_children_reconciliation", **corruption) == [(3, 3)]


def test_duplicate_parent_source_order_is_preserved_and_fails_mart_grain() -> None:
    inputs = {"orders": (*ORDERS, ORDERS[0])}
    assert Counter(run_sql(**inputs)) == Counter(expected_rows(**inputs))
    assert run_sql("order_components_orders_reconciliation", **inputs) == []
    assert run_sql("order_components_grain", **inputs) == [(1,)]
    assert run_sql("order_components_children_reconciliation", **inputs) == [(0, 3)]
