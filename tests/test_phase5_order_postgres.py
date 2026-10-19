"""Native money and clock edges through actual component and order KPI SQL."""

import os
from datetime import datetime
from decimal import Decimal

import pytest
from phase5_native_fixtures import execute_model
from test_phase5_query_postgres import connection as connection
from test_warehouse_order_components_postgres_integration import (
    PARENT_COLUMNS,
    PARENT_TYPES,
    _parent,
)

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_PHASE5_NATIVE") != "1", reason="Explicit isolated native target required"
)
D = Decimal


def parent(identity="a", **changes):
    row = dict(zip(PARENT_COLUMNS, _parent(identity, 41), strict=True))
    row.update(changes)
    for clock, calendar in (
        ("order_purchase_timestamp", "purchase_calendar_date"),
        ("order_delivered_customer_date", "customer_delivery_calendar_date"),
        ("order_estimated_delivery_date", "estimated_delivery_calendar_date"),
    ):
        row[calendar] = row[clock].date() if row[clock] is not None else None
    return tuple(row[column] for column in PARENT_COLUMNS)


def execute_orders(connection, orders, items=(), payments=(), reviews=()):
    fixtures = {
        "fact_orders": (dict(zip(PARENT_COLUMNS, PARENT_TYPES, strict=True)), orders),
        "fact_order_items": (
            dict(
                order_id="text",
                price="numeric(18,2)",
                freight_value="numeric(18,2)",
                is_shipping_before_purchase="boolean",
                is_shipping_beyond_365_days="boolean",
            ),
            [(identity, price, freight, False, False) for identity, price, freight in items],
        ),
        "fact_payments": (
            dict(
                order_id="text",
                payment_value="numeric(18,2)",
                is_zero_installments="boolean",
                is_zero_payment_value="boolean",
                is_undefined_payment_type="boolean",
            ),
            [(identity, value, False, value == 0, False) for identity, value in payments],
        ),
        "fact_reviews": (
            dict(order_id="text", review_score="bigint", is_answer_before_creation="boolean"),
            [(identity, score, False) for identity, score in reviews],
        ),
    }
    rows = execute_model(
        connection, "mart_order_kpis", fixtures, upstream=("mart_order_components",)
    )
    assert len(rows) == len(orders)
    assert len({row["order_id"] for row in rows}) == len(rows)
    return {row["order_id"]: row for row in rows}


@pytest.mark.parametrize(
    "items,payments,sums,known,complete",
    [
        ([], [], (None, None, None), (0, 0, 0), (False, False, False)),
        ([(None, None)], [None], (None, None, None), (0, 0, 0), (False, False, False)),
        (
            [(None, D("0")), (D("0.01"), None)],
            [D("0"), None],
            (D("0.01"), D("0"), D("0")),
            (1, 1, 1),
            (False, False, False),
        ),
        ([(D("0"), D("0"))], [D("0")], (D("0"), D("0"), D("0")), (1, 1, 1), (True, True, True)),
        (
            [(D("1"), None), (D("2"), D("0"))],
            [D("3")],
            (D("3"), D("0"), D("3")),
            (2, 1, 1),
            (True, False, True),
        ),
        (
            [(D("9999999999999999.99"), D("0.01"))] * 2,
            [D("9999999999999999.99")] * 2,
            (D("19999999999999999.98"), D("0.02"), D("19999999999999999.98")),
            (2, 2, 2),
            (True, True, True),
        ),
    ],
    ids=["absent", "all-null", "partial", "measured-zero", "independent-coverage", "headroom"],
)
def test_native_money_coverage_and_aggregate_headroom(
    connection, items, payments, sums, known, complete
):
    row = execute_orders(
        connection,
        [parent()],
        [("a", *item) for item in items],
        [("a", value) for value in payments],
        [("a", score) for score in (1, 4, 5)],
    )["a"]
    assert (row["item_count"], row["payment_count"], row["review_count"]) == (
        len(items),
        len(payments),
        3,
    )
    for column, value in zip(
        ("source_price_sum", "source_freight_sum", "source_payment_sum"), sums, strict=True
    ):
        assert row[column] == value
        assert row[column] is None or isinstance(row[column], Decimal)
    assert tuple(row[key] for key in ("priced_items", "freight_items", "valued_payments")) == known
    assert (
        tuple(
            row[key] for key in ("is_price_complete", "is_freight_complete", "is_payment_complete")
        )
        == complete
    )
    assert row["review_score_sum"] == 10 and row["scored_reviews"] == 3
    assert row["is_commerce_eligible"] is True and row["_source_row"] == 41


@pytest.mark.parametrize("timezone", ["UTC", "Pacific/Honolulu"])
def test_native_clock_boundaries_keep_naive_calendar_policy(connection, timezone):
    connection.execute("SELECT set_config('TimeZone',%s,true)", (timezone,))
    purchase = datetime(2020, 2, 29, 12)
    actual = datetime(2020, 3, 1, 12)
    estimate = datetime(2020, 3, 1)
    cases = [
        ("same-day", {}, (True, True, False, True, 86400, 43200)),
        (
            "equal",
            {"order_delivered_customer_date": estimate},
            (True, True, False, False, 43200, 0),
        ),
        (
            "early",
            {"order_delivered_customer_date": datetime(2020, 2, 29, 18)},
            (True, True, False, False, 21600, -21600),
        ),
        (
            "next-day",
            {"order_delivered_customer_date": datetime(2020, 3, 2)},
            (True, True, True, True, 129600, 86400),
        ),
        (
            "missing-actual",
            {"order_delivered_customer_date": None},
            (False, False, None, None, None, None),
        ),
        (
            "reversed-actual",
            {"order_delivered_customer_date": datetime(2020, 2, 29, 11, 59, 59)},
            (False, False, None, None, None, None),
        ),
        (
            "missing-purchase",
            {"order_purchase_timestamp": None},
            (False, False, None, None, None, None),
        ),
        (
            "missing-estimate",
            {"order_estimated_delivery_date": None},
            (True, False, None, None, 86400, None),
        ),
        (
            "reversed-estimate",
            {"order_estimated_delivery_date": datetime(2020, 2, 29, 11, 59, 59)},
            (True, False, None, None, 86400, None),
        ),
    ]
    defaults = dict(
        order_purchase_timestamp=purchase,
        order_delivered_customer_date=actual,
        order_estimated_delivery_date=estimate,
    )
    rows = execute_orders(
        connection, [parent(identity, **(defaults | changes)) for identity, changes, _ in cases]
    )
    for identity, _, expected in cases:
        row = rows[identity]
        assert row["is_commerce_eligible"] is True
        assert (
            tuple(
                row[key]
                for key in (
                    "is_delivery_eligible",
                    "is_promise_eligible",
                    "is_calendar_late",
                    "is_timestamp_late",
                    "delivery_seconds",
                    "promise_difference_seconds",
                )
            )
            == expected
        )


def test_native_literal_noncommerce_status_and_empty_population(connection):
    statuses = [None, "canceled", "unavailable", "Delivered", "delivered "]
    rows = execute_orders(
        connection,
        [parent(str(index), order_status=status) for index, status in enumerate(statuses)],
    )
    for index, status in enumerate(statuses):
        row = rows[str(index)]
        assert row["order_status"] == status
        assert row["is_commerce_eligible"] is row["is_delivery_eligible"] is False
        assert row["is_promise_eligible"] is False
        assert row["delivery_seconds"] is row["is_calendar_late"] is None
    assert execute_orders(connection, []) == {}
