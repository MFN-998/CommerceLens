"""Actual KPI SQL against tiny in-memory fixtures; no source, credentials or network.

SQLite adapters cover portable joins/eligibility/weighting. Binary-exact review
fixtures do not prove PostgreSQL numeric precision; native acceptance remains required.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = (
    "order_id",
    "order_status",
    "order_purchase_timestamp",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "customer_delivery_calendar_date",
    "estimated_delivery_calendar_date",
    "item_count",
    "payment_count",
    "review_count",
    "source_price_sum",
    "source_freight_sum",
    "source_payment_sum",
    "_source_row",
    "customer_unique_id",
    "is_missing_approval",
)


def order(identifier: str = "a", **changes: object) -> dict[str, object]:
    row: dict[str, object] = dict(
        zip(
            COLUMNS,
            (
                identifier,
                "delivered",
                "2018-01-01 12:00:00",
                "2018-01-03 12:00:00",
                "2018-01-03 00:00:00",
                "2018-01-03",
                "2018-01-03",
                2,
                2,
                2,
                1.5,
                0.5,
                2.0,
                41,
                "same-customer",
                True,
            ),
            strict=True,
        )
    )
    row.update(changes)
    return row


def execute(
    orders: list[dict[str, object]],
    items: list[tuple[object, ...]] | None = None,
    payments: list[tuple[object, ...]] | None = None,
    reviews: list[tuple[object, ...]] | None = None,
) -> list[dict[str, object]]:
    sql = (ROOT / "dbt/models/marts/mart_order_kpis.sql").read_text("utf-8-sig")
    sql = re.sub(r"{{ ref\('([a-z_]+)'\) }}", r"\1", sql)
    sql = sql.replace('collate "C"', "collate BINARY")
    sql = sql.replace("::numeric", " * 1.0").replace("::text", "")
    sql = re.sub(r"extract\(epoch from \((\w+) - (\w+)\)\)", r"seconds(\1, \2)", sql)
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        connection.create_function(
            "seconds",
            2,
            lambda a, b: (datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds(),
        )
        connection.execute("create table mart_order_components (" + ",".join(COLUMNS) + ")")
        connection.executemany(
            "insert into mart_order_components values (" + ",".join("?" for _ in COLUMNS) + ")",
            [tuple(r[c] for c in COLUMNS) for r in orders],
        )
        connection.execute("create table fact_order_items (order_id, price, freight_value)")
        connection.execute("create table fact_payments (order_id, payment_value)")
        connection.execute("create table fact_reviews (order_id, review_score)")
        connection.executemany(
            "insert into fact_order_items values (?,?,?)",
            [("a", 1.0, 0.25), ("a", 0.5, 0.25)] if items is None else items,
        )
        connection.executemany(
            "insert into fact_payments values (?,?)",
            [("a", 1.0), ("a", 1.0)] if payments is None else payments,
        )
        connection.executemany(
            "insert into fact_reviews values (?,?)",
            [("a", 1), ("a", 5)] if reviews is None else reviews,
        )
        connection.execute("pragma query_only=on")
        return [dict(row) for row in connection.execute(sql)]


def test_children_do_not_multiply_order_and_preserve_context() -> None:
    result = execute([order()])
    assert len(result) == 1
    row = result[0]
    assert row["source_price_sum"] == 1.5
    assert row["_source_row"] == 41
    assert row["customer_unique_id"] == "same-customer"
    assert row["is_missing_approval"] == 1
    assert row["priced_items"] == row["valued_payments"] == 2
    assert row["order_review_score"] == 3
    assert row["order_low_review_fraction"] == row["order_high_review_fraction"] == 0.5
    assert row["delivery_seconds"] == 172800
    assert row["is_calendar_late"] == 0
    assert row["is_timestamp_late"] == 1
    assert row["promise_difference_seconds"] == 43200


@pytest.mark.parametrize("status", ["canceled", "unavailable", "Delivered", "delivered "])
def test_literal_noncommerce_status_retained(status: str) -> None:
    row = execute([order(order_status=status)])[0]
    assert row["is_commerce_eligible"] == row["is_delivery_eligible"] == 0
    assert row["delivery_seconds"] is None
    assert row["is_calendar_late"] is None
    assert row["source_price_sum"] == 1.5


def test_absent_partial_and_zero_amounts_are_distinct() -> None:
    absent = execute(
        [order(item_count=0, payment_count=0, review_count=0, source_price_sum=None)], [], [], []
    )[0]
    assert absent["is_price_complete"] == absent["is_payment_complete"] == 0
    assert absent["order_review_score"] is None
    partial = execute([order()], [("a", None, 0.0), ("a", 0.0, 0.0)])[0]
    assert partial["priced_items"] == 1
    assert partial["is_price_complete"] == 0
    assert partial["is_freight_complete"] == 1
    zeros = execute([order()], [("a", 0.0, 0.0), ("a", 0.0, 0.0)], [("a", 0.0), ("a", 0.0)])[0]
    assert zeros["is_price_complete"] == zeros["is_payment_complete"] == 1


def test_promise_reversal_does_not_change_commerce_or_duration() -> None:
    row = execute([order(order_estimated_delivery_date="2017-12-31 00:00:00")])[0]
    assert row["is_commerce_eligible"] == row["is_delivery_eligible"] == 1
    assert row["is_promise_eligible"] == 0
    assert row["is_calendar_late"] is row["promise_difference_seconds"] is None


@pytest.mark.parametrize("actual", [None, "2018-01-01 11:59:59"])
def test_invalid_delivery_has_no_operational_measure(actual: str | None) -> None:
    row = execute([order(order_delivered_customer_date=actual)])[0]
    assert row["is_commerce_eligible"] == 1
    assert row["is_delivery_eligible"] == row["is_promise_eligible"] == 0
    assert row["delivery_seconds"] is None


def test_equal_order_weight_avoids_pair_weight_and_selects_no_review() -> None:
    rows = execute(
        [order(), order("b", review_count=1)],
        reviews=[
            ("a", 1),
            ("a", 1),
            ("b", 5),
        ],
    )
    assert len(rows) == 2
    # Independent hand-calculated equal-order score is3; pair-weighted score is7/3.
    assert sum(r["order_review_score"] for r in rows) / len(rows) == 3
    assert sum(r["order_low_review_fraction"] for r in rows) / len(rows) == 0.5
    assert sum(r["scored_reviews"] for r in rows) == 3


def test_equal_timestamp_and_next_calendar_day_boundaries() -> None:
    equal = execute([order(order_delivered_customer_date="2018-01-03 00:00:00")])[0]
    assert equal["is_timestamp_late"] == equal["is_calendar_late"] == 0
    late = execute(
        [
            order(
                order_delivered_customer_date="2018-01-04 00:00:00",
                customer_delivery_calendar_date="2018-01-04",
            )
        ]
    )[0]
    assert late["is_timestamp_late"] == late["is_calendar_late"] == 1


def test_empty_population() -> None:
    assert execute([]) == []
