"""Synthetic regression checks for consequential exploratory analysis boundaries."""

import hashlib
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from src.analysis import eda
from src.analysis.eda import analyze, cents, days, join, wilson
from src.validation.contracts import TABLES


@pytest.fixture
def sample():
    def frame(name, rows):
        return pd.DataFrame([{**dict.fromkeys(TABLES[name].columns, ""), **r} for r in rows])

    return {
        "orders": frame(
            "orders",
            [
                {
                    "order_id": o,
                    "customer_id": c,
                    "order_status": status,
                    "order_purchase_timestamp": "2018-01-01 00:00:00",
                    "order_approved_at": "2018-01-01 00:00:00",
                    "order_delivered_carrier_date": "2018-01-02 00:00:00",
                    "order_delivered_customer_date": "2018-01-03 12:00:00" if o == "o1" else "",
                    "order_estimated_delivery_date": "2018-01-03 00:00:00",
                }
                for o, c, status in (("o1", "c1", "delivered"), ("o2", "c2", "created"))
            ],
        ),
        "customers": frame(
            "customers",
            [
                {
                    "customer_id": c,
                    "customer_unique_id": "u1",
                    "customer_state": "SP",
                    "customer_zip_code_prefix": "01",
                }
                for c in ("c1", "c2")
            ],
        ),
        "order_items": frame(
            "order_items",
            [
                {
                    "order_id": "o1",
                    "order_item_id": str(i),
                    "product_id": "p1",
                    "seller_id": "s1",
                    "price": "0.10",
                    "freight_value": "0.02",
                }
                for i in (1, 2)
            ],
        ),
        "order_payments": frame(
            "order_payments",
            [
                {
                    "order_id": "o1",
                    "payment_sequential": str(i),
                    "payment_type": "credit_card",
                    "payment_installments": "1",
                    "payment_value": "0.12",
                }
                for i in (1, 2)
            ],
        ),
        "order_reviews": frame(
            "order_reviews",
            [
                {"order_id": "o1", "review_id": r, "review_score": score}
                for r, score in (("r1", "1"), ("r2", "5"))
            ],
        ),
        "products": frame("products", [{"product_id": "p1", "product_category_name": "cat"}]),
        "category_translation": frame(
            "category_translation",
            [{"product_category_name": "cat", "product_category_name_english": "category"}],
        ),
        "sellers": frame(
            "sellers", [{"seller_id": "s1", "seller_state": "SP", "seller_zip_code_prefix": "01"}]
        ),
        "geolocation": frame(
            "geolocation",
            [
                {
                    "geolocation_zip_code_prefix": "01",
                    "geolocation_city": "city",
                    "geolocation_state": "SP",
                }
            ],
        ),
    }


def test_exact_money_and_missing_children_without_fanout(sample):
    result = analyze(sample)
    assert result["sales"]["price_cents"] == 20
    assert result["sales"]["payment_cents"] == 24
    assert result["population"]["orders"] == 2
    assert result["population"]["missing_items"] == 1
    created = next(r for r in result["sales"]["statuses"] if r["order_status"] == "created")
    assert created["price_cents"] is None
    assert result["products"]["categories"][0]["eligible"] == 1
    assert result["payments"]["exact_match_orders"] == 1
    # Identifiers and comment text never enter exported evidence.
    encoded = json.dumps(result)
    assert all(token not in encoded for token in ('"o1"', '"c1"', '"u1"', '"p1"', '"s1"'))


def test_lateness_boundaries_and_multiple_reviews(sample):
    result = analyze(sample)
    assert result["logistics"]["late_timestamp"] == 1
    assert result["logistics"]["late_date"] == 0
    assert result["reviews"]["calendar_lateness"]["all_pairs"][0]["reviews"] == 2
    assert result["reviews"]["calendar_lateness"]["single_review_orders"] == []


@pytest.mark.parametrize("table", ["orders", "order_items", "order_payments", "order_reviews"])
def test_duplicate_declared_grain_fails(sample, table):
    sample[table] = pd.concat([sample[table], sample[table].iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError):
        analyze(sample)


def test_orphan_review_fails(sample):
    sample["order_reviews"].loc[0, "order_id"] = "absent"
    with pytest.raises(ValueError, match="Child order membership"):
        analyze(sample)


@pytest.mark.parametrize("text", ["0.001", "NaN", "-1", "1e2"])
def test_unsupported_money_fails(text):
    with pytest.raises(ValueError):
        cents(text)


def test_money_preserves_large_decimal():
    assert cents("9999999999999999.99") == 999999999999999999
    assert cents("0.10") + cents("0.20") == 30


def test_pair_specific_duration_eligibility():
    start = pd.Series(pd.to_datetime(["2018-01-02", "2018-01-02", None]))
    end = pd.Series(pd.to_datetime(["2018-01-01", "2018-01-02", "2018-01-03"]))
    result = days(start, end)
    assert result.isna().tolist() == [True, False, True]
    assert result.iloc[1] == 0


def test_relationship_missing_or_duplicate_refused():
    with pytest.raises(ValueError):
        join(pd.DataFrame({"key": ["a"]}), pd.DataFrame({"key": ["b"]}), "key")
    with pytest.raises(ValueError):
        join(pd.DataFrame({"key": ["a"]}), pd.DataFrame({"key": ["a", "a"]}), "key")


def test_interval_empty_and_extreme_counts():
    assert wilson(0, 0) is None
    assert wilson(0, 10)[1] > 0
    assert wilson(10, 10)[0] < 1
    with pytest.raises(ValueError):
        wilson(11, 10)


def test_receipt_hash_matches_written_bytes_and_fresh_runs(monkeypatch, tmp_path):
    plan = SimpleNamespace(fingerprint="synthetic", manifest_sha256="synthetic", tables={})
    monkeypatch.setattr(eda, "prepare_source", lambda root: plan)
    monkeypatch.setattr(eda, "iter_source_rows", lambda root, name: [])
    monkeypatch.setattr(eda, "analyze", lambda tables: {"synthetic_count": 1})
    first = eda.run(tmp_path, tmp_path / "evidence")
    second = eda.run(tmp_path, tmp_path / "evidence")
    assert first != second
    assert (first / "results.json").read_bytes() == (second / "results.json").read_bytes()
    receipt = json.loads((first / "receipt.json").read_text())
    assert (
        receipt["results_sha256"]
        == hashlib.sha256((first / "results.json").read_bytes()).hexdigest()
    )


def test_source_change_blocks_publication(monkeypatch, tmp_path):
    plans = iter([SimpleNamespace(), SimpleNamespace(changed=True)])
    monkeypatch.setattr(eda, "prepare_source", lambda root: next(plans))
    monkeypatch.setattr(eda, "iter_source_rows", lambda root, name: [])
    monkeypatch.setattr(eda, "analyze", lambda tables: {})
    with pytest.raises(ValueError, match="Source changed"):
        eda.run(tmp_path, tmp_path / "evidence")
    assert not (tmp_path / "evidence").exists()
