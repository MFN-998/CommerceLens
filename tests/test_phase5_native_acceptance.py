"""Failures in native/source comparison must never produce accepted evidence."""

import json
from decimal import Decimal
from time import monotonic

import pytest

from scripts import verify_phase5_native as acceptance
from src.analytics.measurement import Deadline


def budget():
    return Deadline(monotonic() + 30)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "extra", "money", "null", "boolean"])
def test_row_comparison_rejects_population_and_semantic_changes(fault):
    expected = {"private-key": {"order_id": "private-key", "amount": Decimal("0.30"), "flag": True}}
    row = dict(expected["private-key"])
    rows = [row]
    if fault == "missing":
        rows = []
    elif fault == "duplicate":
        rows.append(row)
    elif fault == "extra":
        row["order_id"] = "unexpected-private-key"
    elif fault == "money":
        row["amount"] = Decimal("0.31")
    elif fault == "null":
        row["amount"] = None
    else:
        row["flag"] = 1
    with pytest.raises(ValueError) as error:
        acceptance.compare_rows(expected, rows, ("order_id",), budget())
    assert "private-key" not in str(error.value)


def test_exact_digest_preserves_large_values_and_normalizes_numeric_scale():
    expected = {
        ("private", 1): {
            "order_id": "private",
            "order_item_id": 1,
            "price": Decimal("9999999999999999.99"),
            "sum": 3,
        }
    }
    row = {**expected[("private", 1)], "sum": Decimal("3.0000")}
    result = acceptance.compare_rows(expected, [row], ("order_id", "order_item_id"), budget())
    assert result["source_sha256"] == result["native_sha256"]
    assert result["rows"] == 1 and "private" not in json.dumps(result)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, statement, *args):
        return Cursor(self.rows)


@pytest.mark.parametrize(
    "kind,modifier", [("float8", -1), ("numeric", -1), ("numeric", (16 << 16) + 6)]
)
def test_native_component_type_or_precision_drift_rejected(kind, modifier):
    rows = [
        (column, typename, (18 << 16) + 6 if column in ("price", "freight_value") else -1)
        for column, typename in acceptance.ITEM_TYPES.items()
    ]
    rows = [
        (column, kind, modifier) if column == "price" else (column, typename, mod)
        for column, typename, mod in rows
    ]
    with pytest.raises(ValueError):
        acceptance.verify_types(Connection(rows), "mart_item_kpis", budget())


def test_aggregate_cannot_inherit_component_headroom():
    rows = [
        (column, kind, (18 << 16) + 6 if column == "source_price_sum" else -1)
        for column, kind in acceptance.ORDER_TYPES.items()
    ]
    with pytest.raises(ValueError, match="aggregate precision"):
        acceptance.verify_types(Connection(rows), "mart_order_kpis", budget())


def test_review_weights_are_exact_and_order_equal():
    base = dict(
        is_commerce_eligible=True,
        is_delivery_eligible=True,
        is_promise_eligible=True,
        is_calendar_late=False,
        is_timestamp_late=True,
        is_price_complete=True,
        is_freight_complete=True,
        is_payment_complete=True,
    )
    rows = {
        "a": {
            **base,
            "review_count": 3,
            "scored_reviews": 3,
            "review_score_sum": 10,
            "low_review_count": 1,
            "high_review_count": 2,
        },
        "b": {
            **base,
            "review_count": 1,
            "scored_reviews": 1,
            "review_score_sum": 1,
            "low_review_count": 1,
            "high_review_count": 0,
        },
    }
    result = acceptance.population_summary(rows)
    assert result["equal_order_review_numerators"] == {
        "review_score_sum": "13/3",
        "low_review_count": "4/3",
        "high_review_count": "2/3",
    }
    assert result["reviewed_delivered_orders"] == 2
    assert result["calendar_late"] == 0 and result["timestamp_late"] == 2


def test_target_failure_stops_before_database_and_suppresses_details(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)

    def reject(*args):
        raise ValueError("private-setting-detail")

    monkeypatch.setattr(acceptance, "_isolated_root", reject)
    monkeypatch.setattr(acceptance, "run_bounded_measurement", lambda *a: pytest.fail("dispatched"))
    monkeypatch.setattr(
        "sys.argv", ["verify", "--settings-root", str(tmp_path), "--expected-project-ref", "a" * 20]
    )
    assert acceptance.main() == 1
    assert "private-setting-detail" not in capsys.readouterr().out
    folder = next((tmp_path / ".artifacts/phase-5").iterdir())
    assert json.loads((folder / "failure.json").read_text())["read_only"] is True
    assert not (folder / "acceptance-receipt.json").exists()
