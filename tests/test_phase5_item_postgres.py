"""Opt-in native item edges using unchanged mart SQL and typed synthetic CTEs."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from phase5_native_fixtures import execute_model
from test_phase5_item_kpis import ITEM_COLUMNS, PRODUCT_COLUMNS, item, product
from test_phase5_query_postgres import connection as connection

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_PHASE5_NATIVE") != "1",
    reason="Phase5 native checks require explicit isolated-target opt-in",
)

ITEM_TYPES = dict(
    zip(
        ITEM_COLUMNS,
        (
            "uuid",
            "bigint",
            "text",
            "bigint",
            "text",
            "text",
            "timestamp",
            "numeric(18,2)",
            "numeric(18,2)",
            "timestamp",
            "uuid",
            "bigint",
            "boolean",
            "boolean",
            "date",
        ),
        strict=True,
    )
)
PRODUCT_TYPES = dict(
    zip(
        PRODUCT_COLUMNS,
        ("text", "uuid", "bigint", "text", "text", "boolean", "boolean"),
        strict=True,
    )
)


def native_item(**changes):
    row = item()
    row.update(
        _load_id=UUID(int=1),
        order_load_id=UUID(int=2),
        shipping_limit_date=datetime(2018, 1, 1, 11, 59, 59),
        price=Decimal("9999999999999999.99"),
        freight_value=Decimal("0.00"),
        order_purchase_timestamp=datetime(2018, 1, 1, 12),
        shipping_calendar_date=date(2018, 1, 1),
    )
    row.update(changes)
    return row


def native_product(identifier="p", category="café ", english="coffee"):
    values = list(product(identifier, category, english))
    values[1] = UUID(int=3)
    return tuple(values)


def execute_items(connection, items, *, orders=None, products=None):
    return execute_model(
        connection,
        "mart_item_kpis",
        {
            "fact_order_items": (
                ITEM_TYPES,
                [tuple(row[column] for column in ITEM_COLUMNS) for row in items],
            ),
            "fact_orders": (
                {"order_id": "text", "order_status": "text"},
                [("a", "delivered")] if orders is None else orders,
            ),
            "dim_product": (
                PRODUCT_TYPES,
                [native_product()] if products is None else products,
            ),
        },
    )


@pytest.mark.parametrize("missing", ["order", "product", "both"])
def test_native_missing_item_parents_retain_rows_and_explicit_flags(connection, missing):
    missing_order = missing in ("order", "both")
    missing_product = missing in ("product", "both")
    source = native_item()
    if missing_order:
        source.update(
            order_load_id=None,
            order_source_row=None,
            order_purchase_timestamp=None,
            is_shipping_before_purchase=False,
        )
    rows = execute_items(
        connection,
        [source],
        orders=[] if missing_order else None,
        products=[] if missing_product else None,
    )
    assert len(rows) == 1
    row = rows[0]
    assert {column: row[column] for column in ITEM_COLUMNS} == source
    assert row["is_missing_order"] is missing_order
    assert row["is_missing_product"] is missing_product
    assert row["is_commerce_eligible"] is not missing_order
    assert row["order_status"] == (None if missing_order else "delivered")
    if missing_product:
        for field in (
            "product_load_id",
            "product_source_row",
            "product_category_name",
            "product_category_name_english",
            "is_missing_category",
            "is_untranslated_category",
        ):
            assert row[field] is None
    else:
        assert row["is_missing_category"] is False
        assert row["is_untranslated_category"] is False


def test_native_item_categories_and_parent_identities_remain_literal(connection):
    categories = [None, "", "café ", "café", "Café", "unmapped"]
    identities = ["p", "P", "two", "three", "four", "five"]
    rows = execute_items(
        connection,
        [
            native_item(
                order_id="A" if index == 1 else "a",
                order_item_id=index + 1,
                product_id=identifier,
            )
            for index, identifier in enumerate(identities)
        ],
        orders=[("a", "delivered"), ("A", "canceled")],
        products=[
            native_product(identifier, category, None if index in (0, 5) else "shared label")
            for index, (identifier, category) in enumerate(zip(identities, categories, strict=True))
        ],
    )
    assert len(rows) == 6
    by_product = {row["product_id"]: row for row in rows}
    assert [by_product[key]["product_category_name"] for key in identities] == categories
    assert [by_product[key]["is_missing_category"] for key in identities] == [
        True,
        False,
        False,
        False,
        False,
        False,
    ]
    assert [by_product[key]["is_untranslated_category"] for key in identities] == [
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    assert [by_product[key]["product_category_name_english"] for key in identities] == [
        None,
        "shared label",
        "shared label",
        "shared label",
        "shared label",
        None,
    ]
    assert all(row["is_missing_product"] is False for row in rows)
    assert all(row["is_missing_order"] is False for row in rows)
    assert by_product["p"]["is_commerce_eligible"] is True
    assert by_product["P"]["is_commerce_eligible"] is False
    assert by_product["P"]["order_status"] == "canceled"


def test_native_repeated_item_associations_preserve_grain_and_money(connection):
    rows = execute_items(
        connection,
        [
            native_item(price=Decimal("0.01"), freight_value=Decimal("1.00")),
            native_item(
                _source_row=42,
                order_item_id=2,
                price=Decimal("0.02"),
                freight_value=Decimal("2.00"),
            ),
            native_item(
                _source_row=43,
                order_item_id=3,
                product_id="q",
                seller_id="t",
                price=Decimal("0.03"),
            ),
            native_item(_source_row=44, order_id="b", order_source_row=20, price=Decimal("0.04")),
        ],
        orders=[("a", "delivered"), ("b", "delivered"), ("no-items", "delivered")],
        products=[native_product(), native_product("q", "other", "coffee")],
    )
    assert len(rows) == 4
    assert {(row["order_id"], row["order_item_id"]) for row in rows} == {
        ("a", 1),
        ("a", 2),
        ("a", 3),
        ("b", 1),
    }
    assert sum(row["price"] for row in rows) == Decimal("0.10")
    assert sum(row["freight_value"] for row in rows) == Decimal("3.00")
    assert sum(row["product_category_name"] == "café " for row in rows) == 3
    assert sum(row["product_category_name"] == "other" for row in rows) == 1


def test_native_item_null_zero_large_money_and_lineage_are_exact(connection):
    sources = [
        native_item(price=None, freight_value=Decimal("0.00")),
        native_item(order_item_id=2, price=Decimal("0.00"), freight_value=None),
        native_item(order_item_id=3, freight_value=Decimal("0.01")),
        native_item(order_item_id=4, freight_value=Decimal("0.02")),
    ]
    rows = execute_items(connection, sources)
    assert len(rows) == 4
    by_item = {row["order_item_id"]: row for row in rows}
    for source in sources:
        row = by_item[source["order_item_id"]]
        assert len(row) == 26
        assert {column: row[column] for column in ITEM_COLUMNS} == source
        assert isinstance(row["_load_id"], UUID)
        assert isinstance(row["shipping_limit_date"], datetime)
        assert isinstance(row["shipping_calendar_date"], date)
        for field in ("price", "freight_value"):
            assert row[field] is None or isinstance(row[field], Decimal)
        assert row["policy_version"] == "v1"
        assert row["product_load_id"] == UUID(int=3)
        assert row["product_source_row"] == 23
    assert sum(row["price"] for row in rows if row["price"] is not None) == Decimal(
        "19999999999999999.98"
    )
    assert sum(row["freight_value"] for row in rows if row["freight_value"] is not None) == Decimal(
        "0.03"
    )


def test_native_noncommerce_item_statuses_remain_visible(connection):
    statuses = ["canceled", "unavailable", "Delivered", "delivered ", None]
    rows = execute_items(
        connection,
        [native_item(order_id=str(index)) for index in range(len(statuses))],
        orders=[(str(index), status) for index, status in enumerate(statuses)],
    )
    assert len(rows) == len(statuses)
    by_order = {row["order_id"]: row for row in rows}
    for index, status in enumerate(statuses):
        row = by_order[str(index)]
        assert row["order_status"] == status
        assert row["is_commerce_eligible"] is False
        assert row["is_missing_order"] is False
        assert row["price"] == Decimal("9999999999999999.99")


def test_native_item_shipping_warnings_and_missing_clock_preserve_commerce(connection):
    sources = [
        native_item(),
        native_item(
            order_id="b",
            order_source_row=20,
            order_item_id=2,
            shipping_limit_date=datetime(2019, 1, 2),
            shipping_calendar_date=date(2019, 1, 2),
            is_shipping_before_purchase=False,
            is_shipping_beyond_365_days=True,
        ),
        native_item(
            order_id="c",
            order_source_row=21,
            order_item_id=3,
            order_purchase_timestamp=None,
            is_shipping_before_purchase=False,
        ),
    ]
    rows = execute_items(
        connection,
        sources,
        orders=[("a", "delivered"), ("b", "delivered"), ("c", "delivered")],
    )
    assert len(rows) == 3
    by_item = {row["order_item_id"]: row for row in rows}
    for source in sources:
        row = by_item[source["order_item_id"]]
        assert {column: row[column] for column in ITEM_COLUMNS} == source
        assert row["is_commerce_eligible"] is True


def test_native_empty_item_population_creates_no_synthetic_items(connection):
    assert execute_items(connection, []) == []
