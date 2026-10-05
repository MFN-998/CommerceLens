"""Independent aggregate acceptance and byte-identical replay gate for Phase 4."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(first: Path, replay: Path) -> dict:
    first_bytes = first.read_bytes()
    if first_bytes != replay.read_bytes():
        raise ValueError("Deterministic replay differs")
    for path in (first, replay):
        saved_receipt = json.loads((path.parent / "receipt.json").read_bytes())
        if saved_receipt["results_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("Run receipt differs from saved bytes")
    r = json.loads(first_bytes)
    p, s = r["population"], r["sales"]
    expected = {
        "orders": 99441,
        "items": 112650,
        "payments": 103886,
        "review_pairs": 99224,
        "identities": 96096,
        "missing_items": 775,
        "missing_payments": 1,
        "missing_reviews": 768,
        "multi_review_orders": 547,
    }
    for key, value in expected.items():
        if p[key] != value:
            raise ValueError("Accepted historical population reconciliation failed")
    for key, value in {
        "price_cents": 1359164370,
        "freight_cents": 225190954,
        "payment_cents": 1600887212,
    }.items():
        if s[key] != value:
            raise ValueError("Accepted warehouse exact-money reconciliation failed")
    partitions = [
        (s["monthly"], "orders", p["orders"]),
        (s["statuses"], "orders", p["orders"]),
        (s["monthly"], "price_cents", s["price_cents"]),
        (s["statuses"], "price_cents", s["price_cents"]),
        (s["monthly"], "payment_cents", s["payment_cents"]),
        (r["products"]["categories"], "items", p["items"]),
        (r["products"]["categories"], "price_cents", s["price_cents"]),
        (r["products"]["categories"], "freight_cents", s["freight_cents"]),
        (r["geography"]["customer_states"], "orders", p["orders"]),
        (r["geography"]["customer_states"], "price_cents", s["price_cents"]),
        (r["geography"]["routes"], "eligible", r["logistics"]["eligible_delivery_orders"]),
        (r["payments"]["methods"], "components", p["payments"]),
        (r["payments"]["methods"], "value_cents", s["payment_cents"]),
        (r["payments"]["installments"], "components", p["payments"]),
        (r["payments"]["installments"], "value_cents", s["payment_cents"]),
        (r["logistics"]["monthly"], "eligible", r["logistics"]["eligible_delivery_orders"]),
        (r["logistics"]["monthly"], "late", r["logistics"]["late_date"]),
    ]
    for rows, key, total in partitions:
        if sum(row[key] or 0 for row in rows) != total:
            raise ValueError("Aggregate partition conservation failed")
    if sum(r["reviews"]["score_distribution"].values()) != p["review_pairs"]:
        raise ValueError("Review score conservation failed")
    forbidden = {
        "order_id",
        "customer_id",
        "customer_unique_id",
        "product_id",
        "seller_id",
        "review_id",
        "review_comment_title",
        "review_comment_message",
        "geolocation_lat",
        "geolocation_lng",
    }

    def inspect(value):
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise ValueError("Raw field in aggregate evidence")
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(r)
    return {
        "status": "passed",
        "results_sha256": hashlib.sha256(first_bytes).hexdigest(),
        "deterministic_replay": "byte-identical",
        "per_run_receipt_hashes": "verified against actual file bytes",
        "aggregate_partitions": len(partitions),
        "accepted_population_checks": len(expected),
        "accepted_money_checks": 3,
        "source_rows": sum(r["provenance"]["table_rows"].values()),
        "privacy_field_gate": "passed",
        "database_operations": 0,
        "scope": "Phase 4 source analysis, not live warehouse workload or official KPI policy",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = verify(args.first, args.replay)
        with args.receipt.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
    except Exception:
        print("Phase 4 acceptance failed; details suppressed. Preserve existing evidence.")
        return 1
    print("Phase 4 independent reconciliation, privacy and deterministic replay gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
