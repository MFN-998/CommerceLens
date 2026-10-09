"""Execute item-mart SQL on independent synthetic rows without native access.

Money is stored as exact text to verify unchanged projection, NULLs and large
values. These portable join tests do not establish PostgreSQL numeric acceptance.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
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
    "order_purchase_timestamp",
    "order_load_id",
    "order_source_row",
    "is_shipping_before_purchase",
    "is_shipping_beyond_365_days",
    "shipping_calendar_date",
)
PRODUCT_COLUMNS = (
    "product_id",
    "_load_id",
    "_source_row",
    "product_category_name",
    "product_category_name_english",
    "is_missing_category",
    "is_untranslated_category",
)


def item(**changes: object) -> dict[str, object]:
    row: dict[str, object] = dict(
        zip(
            ITEM_COLUMNS,
            (
                "item-load",
                41,
                "a",
                1,
                "p",
                "s",
                "2018-01-01 11:59:59",
                "9999999999999999.99",
                "0.00",
                "2018-01-01 12:00:00",
                "order-load",
                19,
                True,
                False,
                "2018-01-01",
            ),
            strict=True,
        )
    )
    row.update(changes)
    return row


def product(
    identifier: str = "p", category: str | None = "café ", english: str | None = "coffee"
) -> tuple[object, ...]:
    return (
        identifier,
        "product-load",
        23,
        category,
        english,
        category is None,
        category is not None and english is None,
    )


def execute(
    items: list[dict[str, object]],
    *,
    orders: list[tuple[object, ...]] | None = None,
    products: list[tuple[object, ...]] | None = None,
) -> list[dict[str, object]]:
    sql = (ROOT / "dbt/models/marts/mart_item_kpis.sql").read_text("utf-8-sig")
    sql = re.sub(r"{{ ref\('([a-z_]+)'\) }}", r"\1", sql)
    sql = sql.replace('collate "C"', "collate BINARY").replace("::text", "")
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        # Hostile default collation proves both joins/status use literal identity.
        connection.execute(
            "create table fact_order_items ("
            + ",".join(f"{name} collate NOCASE" for name in ITEM_COLUMNS)
            + ")"
        )
        connection.execute("create table fact_orders (order_id collate NOCASE, order_status)")
        connection.execute(
            "create table dim_product ("
            + ",".join(f"{name} collate NOCASE" for name in PRODUCT_COLUMNS)
            + ")"
        )
        connection.executemany(
            "insert into fact_order_items values (" + ",".join("?" for _ in ITEM_COLUMNS) + ")",
            [tuple(row[name] for name in ITEM_COLUMNS) for row in items],
        )
        connection.executemany(
            "insert into fact_orders values (?,?)",
            [("a", "delivered")] if orders is None else orders,
        )
        connection.executemany(
            "insert into dim_product values (" + ",".join("?" for _ in PRODUCT_COLUMNS) + ")",
            [product()] if products is None else products,
        )
        connection.execute("pragma query_only=on")
        return [dict(row) for row in connection.execute(sql)]


def test_every_item_field_and_parent_lineage_survives_unchanged() -> None:
    source = item()
    row = execute([source])[0]
    assert {name: row[name] for name in ITEM_COLUMNS} == source
    assert row["policy_version"] == "v1"
    assert row["is_commerce_eligible"] == 1
    assert row["is_missing_order"] == row["is_missing_product"] == 0
    assert row["product_load_id"] == "product-load"
    assert row["product_source_row"] == 23
    assert row["product_category_name"] == "café "
    assert row["product_category_name_english"] == "coffee"


def test_repeated_order_product_seller_associations_preserve_item_grain() -> None:
    rows = execute(
        [
            item(price="0.01", freight_value="1.00"),
            item(order_item_id=2, price="0.02", freight_value="2.00"),
            item(order_item_id=3, product_id="q", seller_id="t", price="0.03"),
            item(order_id="b", price="0.04"),
        ],
        orders=[("a", "delivered"), ("b", "delivered"), ("no-items", "delivered")],
        products=[product(), product("q", "other", "coffee")],
    )
    assert {(row["order_id"], row["order_item_id"]) for row in rows} == {
        ("a", 1),
        ("a", 2),
        ("a", 3),
        ("b", 1),
    }
    assert len(rows) == 4
    assert sum(Decimal(row["price"]) for row in rows) == Decimal("0.10")
    assert sum(Decimal(row["freight_value"]) for row in rows) == Decimal("3.00")
    assert sum(row["product_category_name"] == "café " for row in rows) == 3
    assert sum(row["product_category_name"] == "other" for row in rows) == 1


@pytest.mark.parametrize("status", ["canceled", "unavailable", "Delivered", "delivered ", None])
def test_noncommerce_statuses_remain_visible(status: str | None) -> None:
    row = execute([item()], orders=[("a", status)])[0]
    assert row["order_status"] == status
    assert row["is_commerce_eligible"] == 0
    assert row["price"] == "9999999999999999.99"


def test_missing_and_untranslated_categories_are_separate_from_literal_labels() -> None:
    categories = [None, "", "café ", "café", "Café", "unmapped"]
    products = [
        product(str(index), category, None if index in (0, 5) else "shared label")
        for index, category in enumerate(categories)
    ]
    rows = execute(
        [item(order_item_id=index + 1, product_id=str(index)) for index in range(6)],
        products=products,
    )
    assert [row["product_category_name"] for row in rows] == categories
    assert [row["is_missing_category"] for row in rows] == [1, 0, 0, 0, 0, 0]
    assert [row["is_untranslated_category"] for row in rows] == [0, 0, 0, 0, 0, 1]
    assert all(row["is_missing_product"] == 0 for row in rows)


@pytest.mark.parametrize("missing", ["order", "product", "both"])
def test_missing_parents_are_retained_and_explicit(missing: str) -> None:
    row = execute(
        [item()],
        orders=[] if missing in ("order", "both") else None,
        products=[] if missing in ("product", "both") else None,
    )[0]
    assert row["is_missing_order"] == (missing in ("order", "both"))
    assert row["is_missing_product"] == (missing in ("product", "both"))
    if missing in ("order", "both"):
        assert row["is_commerce_eligible"] == 0
        assert row["order_status"] is None
    if missing in ("product", "both"):
        assert row["product_category_name"] is None
        assert row["is_missing_category"] is None
        assert row["is_untranslated_category"] is None
        assert row["product_load_id"] is None
    assert row["price"] == "9999999999999999.99"


def test_parent_joins_remain_literal_under_case_insensitive_database_defaults() -> None:
    rows = execute(
        [item(), item(order_id="A", product_id="P", order_item_id=2)],
        orders=[("a", "delivered"), ("A", "canceled")],
        products=[product(), product("P", "distinct", "other")],
    )
    assert len(rows) == 2
    assert rows[0]["is_commerce_eligible"] == 1
    assert rows[1]["is_commerce_eligible"] == 0
    assert rows[1]["product_category_name"] == "distinct"


def test_null_zero_and_large_exact_amounts_remain_independent() -> None:
    sources = [
        item(price=None, freight_value="0.00"),
        item(order_item_id=2, price="0.00", freight_value=None),
        item(order_item_id=3, price="9999999999999999.99", freight_value="0.01"),
    ]
    rows = execute(sources)
    assert [(row["price"], row["freight_value"]) for row in rows] == [
        (None, "0.00"),
        ("0.00", None),
        ("9999999999999999.99", "0.01"),
    ]


def test_missing_purchase_clock_and_shipping_warnings_do_not_exclude_commerce() -> None:
    row = execute([item(order_purchase_timestamp=None, is_shipping_beyond_365_days=True)])[0]
    assert row["is_commerce_eligible"] == 1
    assert row["order_purchase_timestamp"] is None
    assert row["is_shipping_before_purchase"] == row["is_shipping_beyond_365_days"] == 1


def test_empty_item_population_creates_no_synthetic_items() -> None:
    assert execute([]) == []
