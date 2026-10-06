"""Opt-in PostgreSQL checks of the actual query with bounded synthetic CTE inputs."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.analytics.query import Query, build_query, serialize_row
from src.warehouse.config import connect
from src.warehouse.reconstruction import _isolated_root, _settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_PHASE5_NATIVE") != "1",
    reason="Phase5 native checks require explicit isolated-target opt-in",
)

ORDER_TYPES = {
    "order_id": "text",
    "customer_unique_id": "text",
    "customer_state": "text",
    "is_commerce_eligible": "boolean",
    "order_purchase_timestamp": "timestamp",
    "purchase_calendar_date": "date",
    "order_delivered_customer_date": "timestamp",
    "order_estimated_delivery_date": "timestamp",
    "item_count": "bigint",
    "source_price_sum": "numeric",
    "source_freight_sum": "numeric",
    "priced_items": "bigint",
    "freight_items": "bigint",
    "is_price_complete": "boolean",
    "is_freight_complete": "boolean",
    "payment_count": "bigint",
    "valued_payments": "bigint",
    "source_payment_sum": "numeric",
    "is_payment_complete": "boolean",
    "review_count": "bigint",
    "scored_reviews": "bigint",
    "review_score_sum": "bigint",
    "low_review_count": "bigint",
    "high_review_count": "bigint",
    "delivery_seconds": "numeric",
    "promise_difference_seconds": "numeric",
    "is_delivery_eligible": "boolean",
    "is_promise_eligible": "boolean",
    "is_calendar_late": "boolean",
    "is_timestamp_late": "boolean",
}
ITEM_TYPES = {
    "order_id": "text",
    "product_id": "text",
    "seller_id": "text",
    "product_category_name": "text",
    "price": "numeric",
    "freight_value": "numeric",
    "is_commerce_eligible": "boolean",
    "order_purchase_timestamp": "timestamp",
    "is_missing_category": "boolean",
    "is_untranslated_category": "boolean",
}


def fixtures():
    purchase = datetime(2020, 2, 29)
    template = dict(
        order_id="a",
        customer_unique_id="one",
        customer_state="SP",
        is_commerce_eligible=True,
        order_purchase_timestamp=purchase,
        purchase_calendar_date=date(2020, 2, 29),
        order_delivered_customer_date=datetime(2020, 3, 2, 12),
        order_estimated_delivery_date=datetime(2020, 3, 2),
        item_count=2,
        source_price_sum=Decimal("0.30"),
        source_freight_sum=Decimal("3.00"),
        priced_items=2,
        freight_items=2,
        is_price_complete=True,
        is_freight_complete=True,
        payment_count=2,
        valued_payments=2,
        source_payment_sum=Decimal("0.90"),
        is_payment_complete=True,
        review_count=3,
        scored_reviews=3,
        review_score_sum=7,
        low_review_count=2,
        high_review_count=1,
        delivery_seconds=Decimal(216000),
        promise_difference_seconds=Decimal(43200),
        is_delivery_eligible=True,
        is_promise_eligible=True,
        is_calendar_late=False,
        is_timestamp_late=True,
    )
    other = {
        **template,
        "order_id": "b",
        "customer_state": "RJ",
        "item_count": 1,
        "priced_items": 1,
        "freight_items": 1,
        "review_count": 1,
        "scored_reviews": 1,
        "review_score_sum": 5,
        "low_review_count": 0,
        "high_review_count": 1,
        "source_payment_sum": Decimal("0.30"),
    }
    missing = {
        **template,
        "order_id": "c",
        "customer_unique_id": "two",
        "item_count": 0,
        "priced_items": 0,
        "freight_items": 0,
        "is_price_complete": False,
        "is_freight_complete": False,
        "source_price_sum": None,
        "source_freight_sum": None,
        "payment_count": 0,
        "valued_payments": 0,
        "source_payment_sum": None,
        "is_payment_complete": False,
        "review_count": 0,
        "scored_reviews": 0,
        "review_score_sum": 0,
        "low_review_count": 0,
        "high_review_count": 0,
        "order_delivered_customer_date": None,
        "delivery_seconds": None,
        "promise_difference_seconds": None,
        "is_delivery_eligible": False,
        "is_promise_eligible": False,
        "is_calendar_late": None,
        "is_timestamp_late": None,
    }
    excluded = {**template, "order_id": "d", "is_commerce_eligible": False}
    boundary = {**template, "order_id": "e", "order_purchase_timestamp": datetime(2020, 3, 1)}
    item = dict(
        order_id="a",
        product_id="1" * 32,
        seller_id="2" * 32,
        product_category_name="A",
        price=Decimal("0.10"),
        freight_value=Decimal("1.00"),
        is_commerce_eligible=True,
        order_purchase_timestamp=purchase,
        is_missing_category=False,
        is_untranslated_category=False,
    )
    items = [
        item,
        {
            **item,
            "product_id": "3" * 32,
            "seller_id": "4" * 32,
            "product_category_name": None,
            "price": Decimal("0.20"),
            "freight_value": Decimal("2.00"),
            "is_missing_category": True,
        },
        {**item, "order_id": "b", "price": Decimal("0.30"), "freight_value": Decimal("3.00")},
    ]
    return [template, other, missing, excluded, boundary], items


def execute(connection, query, orders, items):
    sql, parameters = build_query(query)
    ctes = []
    for name, types, rows in [
        ("synthetic_orders", ORDER_TYPES, orders),
        ("synthetic_items", ITEM_TYPES, items),
    ]:
        values = []
        for number, row in enumerate(rows):
            cells = []
            for field, kind in types.items():
                parameter = f"{name}_{number}_{field}"
                parameters[parameter] = row[field]
                cells.append(f"%({parameter})s::{kind}")
            values.append("(" + ",".join(cells) + ")")
        if values:
            ctes.append(name + "(" + ",".join(types) + ") as (values " + ",".join(values) + ")")
        else:
            ctes.append(
                name
                + " as (select "
                + ",".join(f"NULL::{kind} as {field}" for field, kind in types.items())
                + " where false)"
            )
    sql = sql.replace("marts.mart_order_kpis", "synthetic_orders").replace(
        "marts.mart_item_kpis", "synthetic_items"
    )
    sql = "with " + ",".join(ctes) + ", " + sql.removeprefix("with ")
    try:
        cursor = connection.execute(sql, parameters, binary=True)
        names = [column.name for column in cursor.description]
        return [
            serialize_row(dict(zip(names, row, strict=True)), query) for row in cursor.fetchall()
        ]
    except Exception:
        pytest.fail(
            "Native analytics execution or serialization failed; no private detail logged",
            pytrace=False,
        )


@pytest.fixture
def connection():
    try:
        root = Path(os.environ["COMMERCE_PHASE5_SETTINGS_ROOT"])
        ref = os.environ["COMMERCE_PHASE5_PROJECT_REF"]
        root = _isolated_root(root, ref)
        settings = _settings(root, "transformer", ref)
        conn = connect(settings)
    except Exception:
        pytest.fail("Native test connection failed; no private detail logged", pytrace=False)
    with conn, conn.transaction(force_rollback=True):
        conn.execute("SET TRANSACTION READ ONLY")
        yield conn


@pytest.mark.parametrize("timezone", ["UTC", "Pacific/Honolulu"])
def test_native_query_partitions_and_exact_weighting(connection, timezone):
    connection.execute("SELECT set_config('TimeZone',%s,true)", (timezone,))
    orders, items = fixtures()

    def query(**kwargs):
        q = Query(date(2020, 2, 29), date(2020, 3, 1), **kwargs)
        return execute(connection, q, orders, items)

    total = query()[0]
    assert total["orders"] == 3 and total["active_customers"] == 2 and total["units"] == 3
    assert total["known_gmv"] == "0.60" and total["gmv"] is None
    assert total["known_payment_value"] == "1.20" and total["payment_value"] is None
    assert total["mean_review_score"] == "3.666667" and total["low_rating_rate"] == "0.333333"
    assert total["missing_delivery_clock_orders"] == 1 and total["missing_category_items"] == 1
    for group in ("day", "month", "state"):
        groups = query(group=group)
        for field in (
            "orders",
            "units",
            "priced_items",
            "review_pairs",
            "reviewed_orders",
            "delivery_seconds_sum",
            "missing_delivery_clock_orders",
        ):
            assert sum(row[field] for row in groups) == total[field]
        assert sum(Decimal(row["known_gmv"]) for row in groups) == Decimal(total["known_gmv"])
    categories = query(group="category")
    assert sum(row["orders"] for row in categories) == 3  # a appears twice, c has no items
    assert sum(Decimal(row["gmv"]) for row in categories) == Decimal("0.60")
    assert all(row["payment_value"] is None for row in categories)
    assert query(category="A")[0]["orders"] == 2 and query(category="A")[0]["gmv"] == "0.40"
    assert query(missing_category=True)[0]["gmv"] == "0.20"
    assert query(state="SP")[0]["customer_concentration"] == "1.000000"
    assert query(state="RJ")[0]["customer_concentration"] == "0.500000"
    assert query(state="ZZ")[0]["orders"] == 0 and query(state="ZZ")[0]["gmv"] == "0.00"
    assert query(group="state", limit=1, offset=1)[0]["reference_customers"] == 2
    for group, field in [("seller", "seller"), ("product", "product")]:
        rows = query(group=group)
        assert sum(Decimal(row["gmv"]) for row in rows) == Decimal("0.60")
        assert query(**{field: "2" * 32 if group == "seller" else "1" * 32})[0]["gmv"] == "0.40"


def test_native_large_exact_money_and_empty_inputs(connection):
    orders, items = fixtures()
    orders = orders[:1]
    orders[0]["source_price_sum"] = Decimal("19999999999999999.98")
    query = Query(date(2020, 2, 29), date(2020, 3, 1))
    assert execute(connection, query, orders, items[:2])[0]["gmv"] == "19999999999999999.98"
    assert execute(connection, query, [], [])[0]["gmv"] == "0.00"


def test_native_order_view_preserves_exact_components_and_clock_policy(connection):
    # Execute the actual view SQL against typed synthetic base/child relations.
    # Native numeric beyond(18,2) aggregate headroom and independent child fanout
    # are verified here; these fixtures never read warehouse source records.
    model = (
        Path(__file__).resolve().parents[1] / "dbt/models/marts/mart_order_kpis.sql"
    ).read_text("utf-8-sig")
    for name in ("mart_order_components", "fact_order_items", "fact_payments", "fact_reviews"):
        model = model.replace("{{ ref('" + name + "') }}", name)
    prefix = """with mart_order_components as (
        select 'a'::text as order_id, 'delivered'::text as order_status,
            timestamp '2020-02-29 00:00:00' as order_purchase_timestamp,
            timestamp '2020-03-02 12:00:00' as order_delivered_customer_date,
            timestamp '2020-03-02 00:00:00' as order_estimated_delivery_date,
            date '2020-03-02' as customer_delivery_calendar_date,
            date '2020-03-02' as estimated_delivery_calendar_date,
            2::bigint as item_count, 2::bigint as payment_count,
            19999999999999999.98::numeric as source_price_sum,
            0.03::numeric as source_freight_sum, 0.00::numeric as source_payment_sum,
            3::bigint as review_count, 41::bigint as _source_row,
            '00123'::text as customer_zip_code_prefix, true as is_missing_approval
    ), fact_order_items(order_id, price, freight_value) as (
        values ('a',9999999999999999.99::numeric,0.01::numeric),
               ('a',9999999999999999.99::numeric,0.02::numeric)
    ), fact_payments(order_id,payment_value) as (
        values ('a',0.00::numeric),('a',0.00::numeric)
    ), fact_reviews(order_id,review_score) as (
        values ('a',1::bigint),('a',1::bigint),('a',5::bigint)
    ), verified as ("""
    try:
        cursor = connection.execute(prefix + model + ") select * from verified", binary=True)
        names = [column.name for column in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    except Exception:
        pytest.fail(
            "Native order view verification failed; no private detail logged", pytrace=False
        )
    assert len(rows) == 1
    row = rows[0]
    assert row["source_price_sum"] == Decimal("19999999999999999.98")
    assert row["source_freight_sum"] == Decimal("0.03")
    assert row["source_payment_sum"] == Decimal("0.00")
    assert row["priced_items"] == row["valued_payments"] == 2
    assert row["review_score_sum"] == 7 and row["low_review_count"] == 2
    assert row["high_review_count"] == 1 and row["scored_reviews"] == 3
    assert row["is_calendar_late"] is False and row["is_timestamp_late"] is True
    assert row["delivery_seconds"] == Decimal(216000)
    assert row["customer_zip_code_prefix"] == "00123" and row["_source_row"] == 41
    assert row["is_missing_approval"] is True
