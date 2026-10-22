"""Check actual consolidated SQL against independent per-parent expectations.

Query-only SQLite fixtures use binary-exact amounts and literal identity. They do
not prove PostgreSQL physical types, decimal headroom, plans or performance.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime

import pytest

from tests.order_component_sql import render_order_model
from tests.test_warehouse_order_components import (
    COLUMNS,
    ITEM_COLUMNS,
    ITEMS,
    ORDER_COLUMNS,
    ORDER_NORMAL,
    ORDERS,
    PAYMENT_COLUMNS,
    PAYMENTS,
    REVIEW_COLUMNS,
    REVIEWS,
    expected_rows,
)

KPI_COLUMNS = (
    "policy_version",
    "is_commerce_eligible",
    "priced_items",
    "freight_items",
    "valued_payments",
    "is_price_complete",
    "is_freight_complete",
    "is_payment_complete",
    "scored_reviews",
    "order_review_score",
    "order_low_review_fraction",
    "order_high_review_fraction",
    "review_score_sum",
    "low_review_count",
    "high_review_count",
    "is_delivery_eligible",
    "is_promise_eligible",
    "delivery_seconds",
    "is_calendar_late",
    "is_timestamp_late",
    "promise_difference_seconds",
)
SCORED_REVIEWS = tuple((*row, score) for row, score in zip(REVIEWS, (1, 5, 4, 2), strict=True))


def _seconds(later, earlier):
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds()


def _execute(model, *, orders=ORDERS, items=ITEMS, payments=PAYMENTS, reviews=SCORED_REVIEWS):
    ctes, values = [], []
    for name, columns, rows in (
        ("fact_orders", ORDER_COLUMNS, orders),
        ("fact_order_items", ITEM_COLUMNS, items),
        ("fact_payments", PAYMENT_COLUMNS, payments),
        ("fact_reviews", (*REVIEW_COLUMNS, "review_score"), reviews),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    sql = render_order_model(model)
    sql = sql.replace("::numeric", " * 1.0").replace("::text", "")
    sql = re.sub(r"extract\(epoch from \((\w+) - (\w+)\)\)", r"seconds(\1, \2)", sql)
    statement = "with " + ", ".join(ctes) + " select * from (" + sql + ") actual"
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
        connection.create_function("seconds", 2, _seconds)
        connection.execute("pragma query_only=on")
        cursor = connection.execute(statement, values)
        columns = COLUMNS if model == "mart_order_components" else (*COLUMNS, *KPI_COLUMNS)
        assert tuple(column[0] for column in cursor.description) == columns
        return cursor.fetchall()


def _oracle(*, orders=ORDERS, items=ITEMS, payments=PAYMENTS, reviews=SCORED_REVIEWS):
    """Scan literal child records for each parent; do not reuse model aggregate SQL."""
    result = []
    for parent in orders:
        key = parent[2]
        item = [row for row in items if key is not None and row[0] == key]
        payment = [row for row in payments if key is not None and row[0] == key]
        review = [row for row in reviews if key is not None and row[1] == key]
        prices = [row[2] for row in item if row[2] is not None]
        freight = [row[3] for row in item if row[3] is not None]
        amounts = [row[4] for row in payment if row[4] is not None]
        scores = [row[3] for row in review if row[3] is not None]
        low = sum(1 <= score <= 2 for score in scores)
        high = sum(4 <= score <= 5 for score in scores)
        context = dict(zip(ORDER_COLUMNS, parent, strict=True))
        purchase = context["order_purchase_timestamp"]
        actual = context["order_delivered_customer_date"]
        promise = context["order_estimated_delivery_date"]
        commerce = context["order_status"] == "delivered"
        delivery = bool(commerce and purchase and actual and actual >= purchase)
        eligible_promise = bool(delivery and promise and promise >= purchase)
        technical = (
            *parent,
            len(item),
            sum(prices) if prices else None,
            sum(freight) if freight else None,
            sum(row[4] is True for row in item),
            sum(row[5] is True for row in item),
            bool(item),
            len(payment),
            sum(amounts) if amounts else None,
            sum(row[5] is True for row in payment),
            sum(row[6] is True for row in payment),
            sum(row[7] is True for row in payment),
            bool(payment),
            len(review),
            sum(row[2] is True for row in review),
            bool(review),
            len(review) > 1,
        )
        result.append(
            (
                *technical,
                "v1",
                commerce,
                len(prices),
                len(freight),
                len(amounts),
                bool(item) and len(prices) == len(item),
                bool(item) and len(freight) == len(item),
                bool(payment) and len(amounts) == len(payment),
                len(scores),
                sum(scores) / len(scores) if scores else None,
                low / len(scores) if scores else None,
                high / len(scores) if scores else None,
                sum(scores),
                low,
                high,
                delivery,
                eligible_promise,
                _seconds(actual, purchase) if delivery else None,
                (
                    context["customer_delivery_calendar_date"]
                    > context["estimated_delivery_calendar_date"]
                    if eligible_promise
                    else None
                ),
                actual > promise if eligible_promise else None,
                _seconds(actual, promise) if eligible_promise else None,
            )
        )
    return result


def _assert_models(**inputs):
    expected = _oracle(**inputs)
    technical = _execute("mart_order_components", **inputs)
    actual = _execute("mart_order_kpis", **inputs)
    assert Counter(technical) == Counter(row[:49] for row in expected)
    assert Counter(actual) == Counter(expected)
    assert Counter(row[:49] for row in actual) == Counter(technical)
    return [dict(zip((*COLUMNS, *KPI_COLUMNS), row, strict=True)) for row in actual]


def test_full_49_field_technical_contract_and_70_field_kpi_contract_preserve_oracles():
    rows = _assert_models()
    assert Counter(tuple(row[column] for column in COLUMNS) for row in rows) == Counter(
        expected_rows()
    )
    assert Counter(tuple(row[column] for column in ORDER_COLUMNS) for row in rows) == Counter(
        ORDERS
    )
    first = next(row for row in rows if row["order_id"] == "a" * 32)
    assert (first["item_count"], first["payment_count"], first["review_count"]) == (2, 3, 2)
    assert (first["source_price_sum"], first["source_payment_sum"]) == (5.75, 1.75)
    assert first["shipping_before_purchase_count"] == first["answer_before_creation_count"] == 1


@pytest.mark.parametrize("kind", ["absent", "all_null", "partial", "measured_zero"])
def test_missing_null_partial_and_measured_zero_remain_distinct(kind):
    key = ORDER_NORMAL[2]
    if kind == "absent":
        items, payments, reviews = (), (), ()
    else:
        first = None if kind != "measured_zero" else 0.0
        second = None if kind == "all_null" else 0.0
        items = ((key, 1, first, first, None, False), (key, 2, second, 0.0, True, None))
        payments = (
            (key, 1, "voucher", 0, first, True, False, None),
            (key, 2, "credit_card", 1, second, None, True, False),
        )
        reviews = (("r1", key, None, None), ("r2", key, True, second))
    row = _assert_models(orders=(ORDER_NORMAL,), items=items, payments=payments, reviews=reviews)[0]
    assert row["source_price_sum"] == (None if kind in {"absent", "all_null"} else 0.0)
    assert row["is_price_complete"] == row["is_payment_complete"] == (kind == "measured_zero")
    assert row["has_items"] == (kind != "absent")
    assert row["scored_reviews"] == (0 if kind in {"absent", "all_null"} else 1)


@pytest.mark.parametrize("identity", [None, "A" * 32, " a ", "é", "e\u0301", "", "🙂"])
def test_literal_and_null_parent_ids_do_not_attach_other_child_groups(identity):
    parent = (*ORDER_NORMAL[:2], identity, *ORDER_NORMAL[3:])
    inputs = {
        "orders": (parent,),
        "items": (*ITEMS, (identity, 1, 0.5, 0.25, True, False)),
        "payments": (*PAYMENTS, (identity, 1, "voucher", 1, 0.5, False, False, False)),
        "reviews": (*SCORED_REVIEWS, ("new", identity, False, 5)),
    }
    row = _assert_models(**inputs)[0]
    assert (
        row["item_count"]
        == row["payment_count"]
        == row["review_count"]
        == (0 if identity is None else 1)
    )


def test_duplicate_parents_preserve_multiplicity_and_all_lineage_fields():
    changed = list(ORDER_NORMAL)
    changed[0], changed[1], changed[24], changed[26] = (
        "other-load",
        900,
        "other city",
        "customer-load",
    )
    inputs = {"orders": (ORDER_NORMAL, tuple(changed), ORDER_NORMAL)}
    rows = _assert_models(**inputs)
    assert len(rows) == 3
    assert Counter(tuple(row[column] for column in COLUMNS) for row in rows) == Counter(
        expected_rows(**inputs)
    )


def test_equal_order_review_weights_survive_unequal_children_and_null_scores():
    first, second = ORDERS[:2]
    reviews = (
        ("r1", first[2], False, 1),
        ("r2", first[2], True, 1),
        ("r3", first[2], False, None),
        ("r4", second[2], False, 5),
    )
    rows = _assert_models(orders=(first, second), reviews=reviews)
    assert sum(row["order_review_score"] for row in rows) / 2 == 3
    assert sum(row["order_low_review_fraction"] for row in rows) / 2 == 0.5
    assert sum(row["review_score_sum"] for row in rows) == 7
    assert sum(row["scored_reviews"] for row in rows) == 3


def test_empty_parent_population_retains_both_output_contracts():
    assert _assert_models(orders=()) == []
