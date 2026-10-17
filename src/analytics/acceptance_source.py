"""Independent source-row oracle for private Phase 5 native acceptance.

No SQL or query-layer implementation supplies expected values. Returned row maps
are private verification inputs; only aggregate provenance may enter receipts.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

from src.ingestion.olist import sha256_file, verify_raw
from src.validation.contracts import TABLES
from src.warehouse.source import iter_source_rows, parse_money, prepare_source, update_digest

SOURCE_TABLES = (
    "orders",
    "customers",
    "order_items",
    "order_payments",
    "order_reviews",
    "products",
    "category_translation",
)
type SourceRows = dict[str, list[dict[str, str]]]
type OrderRows = dict[str, dict[str, object]]
type ItemRows = dict[tuple[str, int], dict[str, object]]


class AcceptanceSourceError(ValueError):
    """Fixed diagnostic without source values or local paths."""


def _required(value: str) -> str:
    if not isinstance(value, str) or value == "":
        raise AcceptanceSourceError("Required source identity is missing")
    return value


def _integer(value: str) -> int:
    if re.fullmatch(r"[0-9]+", value) is None or not 0 < int(value) <= 9223372036854775807:
        raise AcceptanceSourceError("Invalid source integer")
    return int(value)


def _timestamp(value: str) -> datetime | None:
    if value == "":
        return None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", value) is None:
        raise AcceptanceSourceError("Invalid source timestamp")
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _money(value: str) -> Decimal | None:
    return parse_money(value) if value != "" else None


def _amounts(rows: list[dict[str, str]], column: str) -> tuple[int, Decimal | None]:
    values = [amount for row in rows if (amount := _money(row[column])) is not None]
    # Source numeric(18,2) values and the bounded source snapshot fit well inside
    # this precision even when the caller has changed the Decimal context.
    with localcontext() as context:
        context.prec = 80
        return len(values), sum(values, Decimal(0)) if values else None


def _index(rows: list[dict[str, str]], key: str) -> dict[str, tuple[int, dict[str, str]]]:
    result = {}
    for ordinal, row in enumerate(rows, 1):
        identity = _required(row[key])
        if identity in result:
            raise AcceptanceSourceError("Duplicate source grain")
        result[identity] = (ordinal, row)
    return result


def _seconds(later: datetime, earlier: datetime) -> Decimal:
    elapsed = later - earlier
    return Decimal(elapsed.days * 86400 + elapsed.seconds)


def expectations(tables: SourceRows, load_id: UUID) -> tuple[OrderRows, ItemRows]:
    """Build exact private expectations from seven literal source table populations."""
    try:
        return _expectations(tables, load_id)
    except AcceptanceSourceError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, ArithmeticError):
        raise AcceptanceSourceError("Source expectation validation failed") from None


def _expectations(tables: SourceRows, load_id: UUID) -> tuple[OrderRows, ItemRows]:
    if not isinstance(load_id, UUID) or any(name not in tables for name in SOURCE_TABLES):
        raise AcceptanceSourceError("Source expectation inputs are incomplete")
    orders = _index(tables["orders"], "order_id")
    customers = _index(tables["customers"], "customer_id")
    products = _index(tables["products"], "product_id")
    translations = _index(tables["category_translation"], "product_category_name")
    children: dict[str, dict[str, list[dict[str, str]]]] = {}
    for name, key in (
        ("order_items", "order_item_id"),
        ("order_payments", "payment_sequential"),
        ("order_reviews", "review_id"),
    ):
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        seen: set[tuple[str, str | int]] = set()
        for row in tables[name]:
            parent = _required(row["order_id"])
            child = _required(row[key]) if name == "order_reviews" else _integer(row[key])
            grain = (parent, child)
            if grain in seen:
                raise AcceptanceSourceError("Duplicate source grain")
            if parent not in orders:
                raise AcceptanceSourceError("Required source parent is missing")
            seen.add(grain)
            grouped[parent].append(row)
        children[name] = grouped

    expected_orders: OrderRows = {}
    for identity, (ordinal, row) in orders.items():
        if row["customer_id"] not in customers:
            raise AcceptanceSourceError("Required source parent is missing")
        customer = customers[row["customer_id"]][1]
        purchase = _timestamp(row["order_purchase_timestamp"])
        actual = _timestamp(row["order_delivered_customer_date"])
        estimate = _timestamp(row["order_estimated_delivery_date"])
        commerce = row["order_status"] == "delivered"
        delivery = commerce and purchase is not None and actual is not None and actual >= purchase
        promise = (
            delivery and purchase is not None and estimate is not None and estimate >= purchase
        )
        items = children["order_items"].get(identity, [])
        payments = children["order_payments"].get(identity, [])
        reviews = children["order_reviews"].get(identity, [])
        priced, price = _amounts(items, "price")
        freighted, freight = _amounts(items, "freight_value")
        valued, payment = _amounts(payments, "payment_value")
        scores = [_integer(review["review_score"]) for review in reviews if review["review_score"]]
        if any(score > 5 for score in scores):
            raise AcceptanceSourceError("Invalid source review score")
        expected_orders[identity] = {
            "_load_id": load_id,
            "_source_row": ordinal,
            "order_id": identity,
            "order_status": row["order_status"] or None,
            "customer_unique_id": _required(customer["customer_unique_id"]),
            "customer_state": customer["customer_state"] or None,
            "order_purchase_timestamp": purchase,
            "order_delivered_customer_date": actual,
            "order_estimated_delivery_date": estimate,
            "policy_version": "v1",
            "is_commerce_eligible": commerce,
            "item_count": len(items),
            "source_price_sum": price,
            "source_freight_sum": freight,
            "priced_items": priced,
            "freight_items": freighted,
            "is_price_complete": bool(items) and priced == len(items),
            "is_freight_complete": bool(items) and freighted == len(items),
            "payment_count": len(payments),
            "source_payment_sum": payment,
            "valued_payments": valued,
            "is_payment_complete": bool(payments) and valued == len(payments),
            "review_count": len(reviews),
            "scored_reviews": len(scores),
            "review_score_sum": sum(scores),
            "low_review_count": sum(score <= 2 for score in scores),
            "high_review_count": sum(score >= 4 for score in scores),
            "is_delivery_eligible": delivery,
            "is_promise_eligible": promise,
            "delivery_seconds": _seconds(actual, purchase)
            if delivery and actual is not None and purchase is not None
            else None,
            "is_calendar_late": actual.date() > estimate.date()
            if promise and actual is not None and estimate is not None
            else None,
            "is_timestamp_late": actual > estimate
            if promise and actual is not None and estimate is not None
            else None,
            "promise_difference_seconds": _seconds(actual, estimate)
            if promise and actual is not None and estimate is not None
            else None,
        }

    expected_items: ItemRows = {}
    for ordinal, row in enumerate(tables["order_items"], 1):
        identity = row["order_id"]
        parent_ordinal, order = orders[identity]
        if row["product_id"] not in products:
            raise AcceptanceSourceError("Required source parent is missing")
        product_ordinal, product = products[row["product_id"]]
        category = product["product_category_name"] or None
        translation = translations.get(category) if category is not None else None
        purchase = _timestamp(order["order_purchase_timestamp"])
        shipping = _timestamp(row["shipping_limit_date"])
        item_id = _integer(row["order_item_id"])
        expected_items[(identity, item_id)] = {
            "_load_id": load_id,
            "_source_row": ordinal,
            "order_id": identity,
            "order_item_id": item_id,
            "product_id": row["product_id"],
            "seller_id": _required(row["seller_id"]),
            "shipping_limit_date": shipping,
            "price": _money(row["price"]),
            "freight_value": _money(row["freight_value"]),
            "order_purchase_timestamp": purchase,
            "order_load_id": load_id,
            "order_source_row": parent_ordinal,
            "is_shipping_before_purchase": shipping is not None
            and purchase is not None
            and shipping < purchase,
            "is_shipping_beyond_365_days": shipping is not None
            and purchase is not None
            and shipping - purchase > timedelta(days=365),
            "shipping_calendar_date": shipping.date() if shipping is not None else None,
            "policy_version": "v1",
            "order_status": order["order_status"] or None,
            "is_commerce_eligible": order["order_status"] == "delivered",
            "is_missing_order": False,
            "is_missing_product": False,
            "product_load_id": load_id,
            "product_source_row": product_ordinal,
            "product_category_name": category,
            "product_category_name_english": translation[1]["product_category_name_english"] or None
            if translation is not None
            else None,
            "is_missing_category": category is None,
            "is_untranslated_category": category is not None and translation is None,
        }
    return expected_orders, expected_items


def source_expectations(root: Path) -> tuple[OrderRows, ItemRows, dict[str, object]]:
    """Verify source before/after reading; return private rows and aggregate evidence."""
    try:
        plan = prepare_source(root)
        tables = {}
        for name in SOURCE_TABLES:
            rows = []
            digest = hashlib.sha256()
            for ordinal, values in enumerate(iter_source_rows(root, name), 1):
                update_digest(digest, ordinal, values)
                rows.append(dict(zip(TABLES[name].columns, values, strict=True)))
            if (
                len(rows) != plan.tables[name].rows
                or digest.hexdigest() != plan.tables[name].content_sha256
            ):
                raise AcceptanceSourceError("Source changed during acceptance preparation")
            tables[name] = rows
        orders, items = expectations(tables, plan.load_id)
        if (
            verify_raw(root) != plan.manifest
            or sha256_file(root / "data/source-manifest.json") != plan.manifest_sha256
        ):
            raise AcceptanceSourceError("Source changed during acceptance preparation")
        provenance: dict[str, object] = {
            "source_fingerprint": plan.fingerprint,
            "load_id": str(plan.load_id),
            "manifest_sha256": plan.manifest_sha256,
            "source_file_sha256": {
                name: record["sha256"] for name, record in sorted(plan.manifest["files"].items())
            },
            "tables": {
                name: {
                    "rows": evidence.rows,
                    "content_sha256": evidence.content_sha256,
                    "money": evidence.money,
                }
                for name, evidence in sorted(plan.tables.items())
            },
            "expectation_tables": list(SOURCE_TABLES),
        }
        return orders, items, provenance
    except AcceptanceSourceError:
        raise
    except Exception:
        raise AcceptanceSourceError("Source acceptance preparation failed") from None
