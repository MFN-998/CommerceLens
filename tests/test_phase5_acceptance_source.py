"""Independent hand-calculated source-oracle cases; no network or native database."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from uuid import UUID

import pytest

from src.analytics import acceptance_source as oracle
from src.validation.contracts import TABLES
from src.warehouse.source import SourcePlan, TableEvidence, update_digest

LOAD = UUID("42fd1329-aa84-457c-9eb3-57da97af702d")


def sample() -> oracle.SourceRows:
    return {
        "orders": [
            {
                "order_id": "a",
                "customer_id": "c",
                "order_status": "delivered",
                "order_purchase_timestamp": "2018-01-01 12:00:00",
                "order_delivered_customer_date": "2018-01-03 12:00:00",
                "order_estimated_delivery_date": "2018-01-03 00:00:00",
            }
        ],
        "customers": [{"customer_id": "c", "customer_unique_id": "same", "customer_state": "SP"}],
        "products": [{"product_id": "p", "product_category_name": "café "}],
        "category_translation": [
            {"product_category_name": "café ", "product_category_name_english": "coffee"}
        ],
        "order_items": [
            {
                "order_id": "a",
                "order_item_id": "1",
                "product_id": "p",
                "seller_id": "s",
                "shipping_limit_date": "2018-01-01 11:59:59",
                "price": "0.01",
                "freight_value": "0.00",
            }
        ],
        "order_payments": [{"order_id": "a", "payment_sequential": "1", "payment_value": "0.01"}],
        "order_reviews": [
            {"order_id": "a", "review_id": "r1", "review_score": "1"},
            {"order_id": "a", "review_id": "r2", "review_score": "5"},
        ],
    }


def test_order_policy_money_reviews_and_same_calendar_day_are_independent() -> None:
    orders, items = oracle.expectations(sample(), LOAD)
    row = orders["a"]
    assert row["_load_id"] == LOAD and row["_source_row"] == 1
    assert row["source_price_sum"] == row["source_payment_sum"] == Decimal("0.01")
    assert row["source_freight_sum"] == Decimal("0.00")
    assert row["item_count"] == row["priced_items"] == row["freight_items"] == 1
    assert row["is_price_complete"] is row["is_freight_complete"] is True
    assert row["is_payment_complete"] is True
    assert row["review_count"] == row["scored_reviews"] == 2
    assert row["review_score_sum"] == 6
    assert row["low_review_count"] == row["high_review_count"] == 1
    assert row["is_commerce_eligible"] is row["is_delivery_eligible"] is True
    assert row["is_promise_eligible"] is True
    assert row["delivery_seconds"] == Decimal(172800)
    assert row["is_calendar_late"] is False and row["is_timestamp_late"] is True
    assert row["promise_difference_seconds"] == Decimal(43200)
    assert len(items) == 1


def test_all_26_item_fields_keep_literal_identity_clock_and_lineage() -> None:
    tables = sample()
    tables["orders"].insert(0, {**tables["orders"][0], "order_id": "no-items"})
    tables["products"].insert(0, {"product_id": "unused", "product_category_name": ""})
    _, rows = oracle.expectations(tables, LOAD)
    assert rows[("a", 1)] == {
        "_load_id": LOAD,
        "_source_row": 1,
        "order_id": "a",
        "order_item_id": 1,
        "product_id": "p",
        "seller_id": "s",
        "shipping_limit_date": datetime(2018, 1, 1, 11, 59, 59),
        "price": Decimal("0.01"),
        "freight_value": Decimal("0.00"),
        "order_purchase_timestamp": datetime(2018, 1, 1, 12),
        "order_load_id": LOAD,
        "order_source_row": 2,
        "is_shipping_before_purchase": True,
        "is_shipping_beyond_365_days": False,
        "shipping_calendar_date": date(2018, 1, 1),
        "policy_version": "v1",
        "order_status": "delivered",
        "is_commerce_eligible": True,
        "is_missing_order": False,
        "is_missing_product": False,
        "product_load_id": LOAD,
        "product_source_row": 2,
        "product_category_name": "café ",
        "product_category_name_english": "coffee",
        "is_missing_category": False,
        "is_untranslated_category": False,
    }


def test_absent_partial_zero_and_large_money_with_hostile_decimal_context() -> None:
    tables = sample()
    tables["orders"].append({**tables["orders"][0], "order_id": "empty"})
    tables["order_items"] = [
        {**tables["order_items"][0], "price": "9999999999999999.99", "freight_value": ""},
        {**tables["order_items"][0], "order_item_id": "2", "price": "9999999999999999.99"},
        {**tables["order_items"][0], "order_item_id": "3", "price": ""},
    ]
    tables["order_payments"][0]["payment_value"] = "0.00"
    with localcontext() as context:
        context.prec = 3
        orders, items = oracle.expectations(tables, LOAD)
    assert orders["a"]["source_price_sum"] == Decimal("19999999999999999.98")
    assert orders["a"]["priced_items"] == orders["a"]["freight_items"] == 2
    assert orders["a"]["is_price_complete"] is orders["a"]["is_freight_complete"] is False
    assert orders["a"]["source_payment_sum"] == Decimal("0.00")
    assert orders["a"]["is_payment_complete"] is True
    assert orders["empty"]["source_price_sum"] is orders["empty"]["source_payment_sum"] is None
    assert orders["empty"]["item_count"] == orders["empty"]["review_count"] == 0
    assert orders["empty"]["is_price_complete"] is orders["empty"]["is_payment_complete"] is False
    assert items[("a", 1)]["freight_value"] is items[("a", 3)]["price"] is None


def test_all_missing_amount_families_have_unknown_sums_and_explicit_coverage() -> None:
    tables = sample()
    tables["order_items"][0].update(price="", freight_value="")
    tables["order_payments"][0]["payment_value"] = ""
    tables["order_reviews"][0]["review_score"] = ""
    row = oracle.expectations(tables, LOAD)[0]["a"]
    assert row["source_price_sum"] is row["source_freight_sum"] is row["source_payment_sum"] is None
    assert row["priced_items"] == row["freight_items"] == row["valued_payments"] == 0
    assert row["review_count"] == 2 and row["scored_reviews"] == 1
    assert row["review_score_sum"] == 5


@pytest.mark.parametrize(
    ("purchase", "actual", "estimate", "delivery", "promise", "late", "seconds"),
    [
        ("2018-01-01 12:00:00", "", "2018-01-03 00:00:00", False, False, None, None),
        ("", "2018-01-03 12:00:00", "2018-01-03 00:00:00", False, False, None, None),
        (
            "2018-01-01 12:00:00",
            "2018-01-01 11:59:59",
            "2018-01-03 00:00:00",
            False,
            False,
            None,
            None,
        ),
        ("2018-01-01 12:00:00", "2018-01-03 12:00:00", "", True, False, None, None),
        (
            "2018-01-01 12:00:00",
            "2018-01-03 12:00:00",
            "2018-01-01 11:59:59",
            True,
            False,
            None,
            None,
        ),
        ("2018-01-01 12:00:00", "2018-01-03 00:00:00", "2018-01-03 00:00:00", True, True, False, 0),
        (
            "2018-01-01 12:00:00",
            "2018-01-04 00:00:00",
            "2018-01-03 00:00:00",
            True,
            True,
            True,
            86400,
        ),
        (
            "2018-01-01 12:00:00",
            "2018-01-02 12:00:00",
            "2018-01-03 00:00:00",
            True,
            True,
            False,
            -43200,
        ),
    ],
)
def test_delivery_denominators_and_signed_promise_difference(
    purchase: str,
    actual: str,
    estimate: str,
    delivery: bool,
    promise: bool,
    late: bool | None,
    seconds: int | None,
) -> None:
    tables = sample()
    tables["orders"][0].update(
        order_purchase_timestamp=purchase,
        order_delivered_customer_date=actual,
        order_estimated_delivery_date=estimate,
    )
    row = oracle.expectations(tables, LOAD)[0]["a"]
    assert row["is_commerce_eligible"] is True
    assert row["is_delivery_eligible"] is delivery
    assert row["is_promise_eligible"] is promise
    assert row["is_calendar_late"] is late
    assert row["promise_difference_seconds"] == seconds


@pytest.mark.parametrize("status", ["canceled", "Delivered", "delivered ", ""])
def test_literal_status_never_infers_commerce(status: str) -> None:
    tables = sample()
    tables["orders"][0]["order_status"] = status
    order = oracle.expectations(tables, LOAD)[0]["a"]
    assert order["is_commerce_eligible"] is order["is_delivery_eligible"] is False
    assert order["delivery_seconds"] is None
    assert order["source_price_sum"] == Decimal("0.01")


def test_missing_untranslated_and_literal_categories_do_not_share_a_sentinel() -> None:
    tables = sample()
    categories = ["", "café", "Café", "café ", " "]
    tables["products"] = [
        {"product_id": str(index), "product_category_name": category}
        for index, category in enumerate(categories)
    ]
    tables["order_items"] = [
        {**tables["order_items"][0], "order_item_id": str(index + 1), "product_id": str(index)}
        for index in range(len(categories))
    ]
    items = list(oracle.expectations(tables, LOAD)[1].values())
    assert [row["product_category_name"] for row in items] == [None, "café", "Café", "café ", " "]
    assert [row["is_missing_category"] for row in items] == [True, False, False, False, False]
    assert [row["is_untranslated_category"] for row in items] == [False, True, True, False, True]


def test_equal_order_review_components_and_repeat_customer_identity_remain_unrounded() -> None:
    tables = sample()
    tables["orders"].append({**tables["orders"][0], "order_id": "A", "customer_id": "C"})
    tables["customers"].append(
        {"customer_id": "C", "customer_unique_id": "same", "customer_state": "RJ"}
    )
    tables["order_reviews"] = [
        {"order_id": "a", "review_id": "r1", "review_score": "1"},
        {"order_id": "a", "review_id": "r2", "review_score": "1"},
        {"order_id": "a", "review_id": "r3", "review_score": "5"},
        {"order_id": "A", "review_id": "r1", "review_score": "5"},
    ]
    orders, _ = oracle.expectations(tables, LOAD)
    assert orders["a"]["customer_unique_id"] == orders["A"]["customer_unique_id"] == "same"
    assert orders["a"]["customer_state"] == "SP" and orders["A"]["customer_state"] == "RJ"
    assert orders["a"]["review_score_sum"] == 7 and orders["a"]["scored_reviews"] == 3
    assert orders["A"]["review_score_sum"] == 5 and orders["A"]["scored_reviews"] == 1
    assert (Fraction(7, 3) + 5) / 2 == Fraction(11, 3)
    assert "order_review_score" not in orders["a"]


@pytest.mark.parametrize("name", oracle.SOURCE_TABLES)
def test_duplicate_source_grains_fail_closed(name: str) -> None:
    tables = sample()
    tables[name].append(deepcopy(tables[name][0]))
    with pytest.raises(oracle.AcceptanceSourceError, match="^Duplicate source grain$"):
        oracle.expectations(tables, LOAD)


@pytest.mark.parametrize("name", ["orders", "customers", "products"])
def test_required_parent_absence_fails_without_source_values(name: str) -> None:
    tables = sample()
    tables[name] = []
    with pytest.raises(oracle.AcceptanceSourceError, match="^Required source parent is missing$"):
        oracle.expectations(tables, LOAD)


def test_empty_populations_are_empty_and_inputs_are_unchanged() -> None:
    empty = {name: [] for name in oracle.SOURCE_TABLES}
    assert oracle.expectations(empty, LOAD) == ({}, {})
    tables = sample()
    original = deepcopy(tables)
    oracle.expectations(tables, LOAD)
    assert tables == original


def _mock_source(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[tuple[str, ...]]]:
    tables = sample()
    raw = {
        name: [tuple(row.get(column, "") for column in TABLES[name].columns) for row in rows]
        for name, rows in tables.items()
    }
    evidence = {}
    for name, rows in raw.items():
        digest = hashlib.sha256()
        for ordinal, values in enumerate(rows, 1):
            update_digest(digest, ordinal, values)
        evidence[name] = TableEvidence(len(rows), digest.hexdigest(), {})
    manifest = {"files": {"file.csv": {"sha256": "f" * 64}}}
    plan = SourcePlan(manifest, "a" * 64, LOAD, "b" * 64, evidence)
    monkeypatch.setattr(oracle, "prepare_source", lambda _: plan)
    monkeypatch.setattr(oracle, "iter_source_rows", lambda _, name: iter(raw[name]))
    monkeypatch.setattr(oracle, "verify_raw", lambda _: manifest)
    monkeypatch.setattr(oracle, "sha256_file", lambda _: "b" * 64)
    return raw


def test_source_wrapper_returns_aggregate_provenance_without_private_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_source(monkeypatch)
    orders, items, provenance = oracle.source_expectations(Path("unused"))
    assert len(orders) == len(items) == 1
    assert provenance["load_id"] == str(LOAD)
    assert provenance["source_fingerprint"] == "a" * 64
    assert provenance["manifest_sha256"] == "b" * 64
    assert provenance["expectation_tables"] == list(oracle.SOURCE_TABLES)
    assert "customer_unique_id" not in repr(provenance)
    assert "order_id" not in repr(provenance)


@pytest.mark.parametrize("change", ["row", "manifest", "manifest_bytes"])
def test_changed_source_during_read_is_rejected(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    raw = _mock_source(monkeypatch)
    if change == "row":
        raw["order_items"].append(raw["order_items"][0])
    elif change == "manifest":
        monkeypatch.setattr(oracle, "verify_raw", lambda _: {"files": {}})
    else:
        monkeypatch.setattr(oracle, "sha256_file", lambda _: "c" * 64)
    with pytest.raises(
        oracle.AcceptanceSourceError, match="^Source changed during acceptance preparation$"
    ):
        oracle.source_expectations(Path("unused"))


def test_source_io_errors_have_fixed_safe_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_: Path) -> SourcePlan:
        raise OSError("private-source-path-and-record")

    monkeypatch.setattr(oracle, "prepare_source", broken)
    with pytest.raises(
        oracle.AcceptanceSourceError, match="^Source acceptance preparation failed$"
    ):
        oracle.source_expectations(Path("unused"))
