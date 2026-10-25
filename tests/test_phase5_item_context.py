"""Independent full-row item-mart reconciliation; portable, not native type proof."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing

import pytest
import test_warehouse_fact_orders as order_fixture
from item_projection_sql import (
    ORDER_COLUMNS,
    SOURCE_COLUMNS,
    independent_items,
    render_item_sql,
    staged_orders,
)
from test_phase5_item_kpis import ITEM_COLUMNS, PRODUCT_COLUMNS, item, product
from test_warehouse_fact_order_items import elapsed_seconds, sqlite_statement

COLUMNS = (
    *ITEM_COLUMNS,
    "policy_version",
    "order_status",
    "is_commerce_eligible",
    "is_missing_order",
    "is_missing_product",
    "product_load_id",
    "product_source_row",
    "product_category_name",
    "product_category_name_english",
    "is_missing_category",
    "is_untranslated_category",
)


def render(path):
    sql = render_item_sql(path.removeprefix("dbt/"))
    if path.startswith("dbt/models/"):
        sql = sqlite_statement(sql)
    return sql.replace("::text", "")


def portable_multisets(sql):
    # SQLite lacks EXCEPT ALL: number each equal occurrence to preserve multiplicity.
    def subtract(match):
        left, right = match.groups()
        fields = ",".join(COLUMNS)
        equal = " and ".join(f"l.{c} is r.{c}" for c in COLUMNS)
        return (
            "select "
            + ",".join("l." + c for c in COLUMNS)
            + f" from (select *,row_number() over(partition by {fields}) as occurrence"
            + f" from {left}) l left join (select *,row_number() over(partition by {fields})"
            + f" as occurrence from {right}) r on {equal} and l.occurrence=r.occurrence"
            + " where r.occurrence is null"
        )

    return re.sub(
        r"select \* from (expected|actual)\s+except all\s+select \* from (expected|actual)",
        subtract,
        sql,
        flags=re.IGNORECASE,
    )


def evaluate(
    *,
    staged=(("a", "delivered"),),
    facts=None,
    items=None,
    products=None,
    changes=None,
    duplicate_actual=False,
    reconcile=True,
):
    items = [item()] if items is None else items
    products = [product()] if products is None else products
    facts = staged if facts is None else facts
    expected_items = independent_items(items, facts)
    ctes, values = [], []
    for name, columns, rows in (
        (
            "fact_order_items",
            ITEM_COLUMNS,
            [tuple(row[c] for c in ITEM_COLUMNS) for row in expected_items],
        ),
        (
            "stg_order_items",
            SOURCE_COLUMNS,
            [tuple(row[c] for c in SOURCE_COLUMNS) for row in items],
        ),
        ("stg_orders", ORDER_COLUMNS, staged_orders(items, staged)),
        ("fact_orders", ("order_id", "order_status"), staged if facts is None else facts),
        ("dim_product", PRODUCT_COLUMNS, products),
    ):
        body = (
            "values " + ",".join("(" + ",".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ",".join("null" for _ in columns) + " where false"
        )
        ctes.append(name + "(" + ",".join(columns) + ") as (" + body + ")")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("dbt/models/marts/mart_item_kpis.sql") + ")")
    fields = ",".join((changes or {}).get(c, c) + " as " + c for c in COLUMNS)
    actual = "select " + fields + " from projected"
    if duplicate_actual:
        actual += " union all select * from projected"
    ctes.append("mart_item_kpis as (" + actual + ")")
    query = (
        render("dbt/tests/item_kpis_source_reconciliation.sql")
        if reconcile
        else "select * from mart_item_kpis"
    )
    sql = portable_multisets("with " + ",".join(ctes) + " select * from (" + query + ") result")
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_collation("C", lambda a, b: (a > b) - (a < b))
        connection.create_function("elapsed_seconds", 2, elapsed_seconds)
        connection.execute("pragma query_only=on")
        cursor = connection.execute(sql, values)
        if not reconcile:
            assert tuple(c[0] for c in cursor.description) == COLUMNS
        return cursor.fetchall()


@pytest.mark.parametrize("customers", [order_fixture.CUSTOMERS, order_fixture.CUSTOMERS[1:], ()])
def test_actual_order_fact_matches_staged_status_without_customer_mapping(customers):
    orders = order_fixture.ORDERS[:2]
    derived = order_fixture.run_sql(orders=orders, customers=customers)
    staged = tuple(
        tuple(row[order_fixture.SOURCE_COLUMNS.index(c)] for c in ("order_id", "order_status"))
        for row in orders
    )
    facts = tuple(
        tuple(row[order_fixture.COLUMNS.index(c)] for c in ("order_id", "order_status"))
        for row in derived
    )
    items = [item(order_id=row[0], order_item_id=i + 1) for i, row in enumerate(staged)]
    assert evaluate(staged=staged, facts=facts, items=items) == []
    assert len(evaluate(staged=staged, facts=facts, items=items, reconcile=False)) == len(items)


@pytest.mark.parametrize("status", [None, "delivered", "Delivered", "delivered ", "canceled", ""])
def test_literal_nullable_status_equivalence(status):
    assert evaluate(staged=(("a", status),), facts=(("a", status),)) == []


@pytest.mark.parametrize("field", COLUMNS)
def test_every_output_field_change_fails_independent_reconciliation(field):
    assert evaluate() == []
    assert evaluate(changes={field: "NULL"}) == [(1, 1, 1, 1)]


@pytest.mark.parametrize(
    "staged,facts",
    [
        ((("a", "canceled"),), (("a", "delivered"),)),
        ((), (("a", "delivered"),)),
        ((("a", "delivered"),), ()),
        ((("A", "delivered"),), (("a", "delivered"),)),
    ],
)
def test_separate_order_fixtures_reject_status_or_presence_divergence(staged, facts):
    assert evaluate(staged=staged, facts=facts) == [(1, 1, 1, 1)]


@pytest.mark.parametrize("side", ["staged", "facts", "both"])
def test_duplicate_parent_fanout_is_rejected_even_when_shared(side):
    single = (("a", "delivered"),)
    assert evaluate(
        staged=single * (2 if side in {"staged", "both"} else 1),
        facts=single * (2 if side in {"facts", "both"} else 1),
    )


def test_duplicate_customer_mapping_remains_blocked():
    orders = order_fixture.ORDERS[:1]
    derived = order_fixture.run_sql(
        orders=orders, customers=(*order_fixture.CUSTOMERS, order_fixture.CUSTOMERS[0])
    )
    staged = tuple(
        tuple(row[order_fixture.SOURCE_COLUMNS.index(c)] for c in ("order_id", "order_status"))
        for row in orders
    )
    facts = tuple(
        tuple(row[order_fixture.COLUMNS.index(c)] for c in ("order_id", "order_status"))
        for row in derived
    )
    assert len(facts) > len(staged)
    assert evaluate(staged=staged, facts=facts, items=[item(order_id=staged[0][0])])


def test_missing_parents_null_money_category_and_duplicate_output():
    assert evaluate(staged=(), facts=(), products=[], items=[item(price=None)]) == []
    assert evaluate(items=[], staged=(), facts=()) == []
    assert evaluate(duplicate_actual=True) == [(1, 2, 0, 1)]
    for category in (None, "", "café ", "Café", "unmapped"):
        assert evaluate(products=[product(category=category, english=None)]) == []
    assert evaluate(changes={"product_category_name": "'café'"}) == [(1, 1, 1, 1)]
