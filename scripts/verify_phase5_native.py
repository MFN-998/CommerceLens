"""Read-only, source-independent acceptance of the two already-built KPI views.

Row identities remain in memory. Retained evidence contains only aggregate counts,
digests, types and protected warehouse metadata, never source or database rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from scripts.phase5_native import metadata, write
from src.analytics.acceptance_source import source_expectations
from src.analytics.measurement import Deadline, run_bounded_measurement
from src.ingestion.olist import sha256_file, verify_raw
from src.warehouse.config import ROOT, connect
from src.warehouse.reconstruction import _isolated_root, _settings

ORDER_TYPES = {
    "_load_id": "uuid",
    "_source_row": "int8",
    "order_id": "text",
    "order_status": "text",
    "customer_unique_id": "text",
    "customer_state": "text",
    "order_purchase_timestamp": "timestamp",
    "order_delivered_customer_date": "timestamp",
    "order_estimated_delivery_date": "timestamp",
    "policy_version": "text",
    "is_commerce_eligible": "bool",
    "item_count": "int8",
    "source_price_sum": "numeric",
    "source_freight_sum": "numeric",
    "priced_items": "int8",
    "freight_items": "int8",
    "is_price_complete": "bool",
    "is_freight_complete": "bool",
    "payment_count": "int8",
    "source_payment_sum": "numeric",
    "valued_payments": "int8",
    "is_payment_complete": "bool",
    "review_count": "int8",
    "scored_reviews": "int8",
    "review_score_sum": "numeric",
    "low_review_count": "int8",
    "high_review_count": "int8",
    "is_delivery_eligible": "bool",
    "is_promise_eligible": "bool",
    "delivery_seconds": "numeric",
    "is_calendar_late": "bool",
    "is_timestamp_late": "bool",
    "promise_difference_seconds": "numeric",
}
ITEM_TYPES = {
    "_load_id": "uuid",
    "_source_row": "int8",
    "order_id": "text",
    "order_item_id": "int8",
    "product_id": "text",
    "seller_id": "text",
    "shipping_limit_date": "timestamp",
    "price": "numeric",
    "freight_value": "numeric",
    "order_purchase_timestamp": "timestamp",
    "order_load_id": "uuid",
    "order_source_row": "int8",
    "is_shipping_before_purchase": "bool",
    "is_shipping_beyond_365_days": "bool",
    "shipping_calendar_date": "date",
    "policy_version": "text",
    "order_status": "text",
    "is_commerce_eligible": "bool",
    "is_missing_order": "bool",
    "is_missing_product": "bool",
    "product_load_id": "uuid",
    "product_source_row": "int8",
    "product_category_name": "text",
    "product_category_name_english": "text",
    "is_missing_category": "bool",
    "is_untranslated_category": "bool",
}
CONTRACTS = {"mart_order_kpis": ORDER_TYPES, "mart_item_kpis": ITEM_TYPES}


def canonical(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, Decimal)):
        return {"exact": str(Fraction(value))}
    if isinstance(value, (UUID, datetime, date)):
        return str(value)
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    raise ValueError("Unsupported acceptance value")


def compare_rows(
    expected: Mapping[Any, dict[str, object]],
    rows: Iterable[dict[str, object]],
    keys: tuple[str, ...],
    deadline: Deadline,
) -> dict[str, object]:
    seen = set()
    source_digest, native_digest = hashlib.sha256(), hashlib.sha256()
    for row in rows:
        deadline.check()
        key_parts = tuple(row[name] for name in keys)
        key = key_parts[0] if len(keys) == 1 else key_parts
        if key in seen or key not in expected:
            raise ValueError("Native grain differs from source")
        source = expected[key]
        actual_body = json.dumps(canonical(row), sort_keys=True, separators=(",", ":")).encode()
        source_body = json.dumps(canonical(source), sort_keys=True, separators=(",", ":")).encode()
        if actual_body != source_body:
            raise ValueError("Native policy row differs from source")
        for digest, body in ((source_digest, source_body), (native_digest, actual_body)):
            digest.update(len(body).to_bytes(8, "big"))
            digest.update(body)
        seen.add(key)
    if len(seen) != len(expected) or not seen:
        raise ValueError("Native population differs from source")
    return {
        "rows": len(seen),
        "fields": len(next(iter(expected.values()))),
        "source_sha256": source_digest.hexdigest(),
        "native_sha256": native_digest.hexdigest(),
        "mismatches": 0,
    }


def verify_types(connection: Any, name: str, deadline: Deadline) -> dict[str, str]:
    required = CONTRACTS[name]
    rows = deadline.execute(
        connection,
        "select a.attname,t.typname,a.atttypmod from pg_attribute a "
        "join pg_type t on t.oid=a.atttypid where a.attrelid=%s::regclass "
        "and a.attnum>0 and not a.attisdropped",
        ("marts." + name,),
    ).fetchall()
    found = {column: (kind, modifier) for column, kind, modifier in rows}
    if any(found.get(column, (None,))[0] != kind for column, kind in required.items()):
        raise ValueError("Native column type differs from contract")
    # Source components remain numeric(18,2), while aggregates must retain
    # unconstrained numeric headroom rather than inherit the component limit.
    if name == "mart_item_kpis":
        if any(found[column][1] != (18 << 16) + 2 + 4 for column in ("price", "freight_value")):
            raise ValueError("Native component precision differs")
    elif any(
        found[column][1] != -1
        for column in (
            "source_price_sum",
            "source_freight_sum",
            "source_payment_sum",
            "review_score_sum",
        )
    ):
        raise ValueError("Native aggregate precision is constrained")
    return dict(required)


def native_rows(connection: Any, name: str, deadline: Deadline) -> Iterable[dict[str, object]]:
    columns = tuple(CONTRACTS[name])
    # Relation, projection and ordering are fixed internal allowlists.
    sql = "select " + ",".join(columns) + " from marts." + name
    sql += ' order by order_id collate "C"' + (",order_item_id" if name == "mart_item_kpis" else "")
    # Acceptance consumes every row. The default cursor estimate favors early
    # rows and chose costly nested loops for the expanded item view. Keep this
    # setting transaction-local; consumer workload planning is a separate gate.
    deadline.execute(connection, "SET LOCAL cursor_tuple_fraction=1.0")
    with connection.cursor(name="phase5_acceptance") as cursor:
        deadline.execute(connection, "SELECT 1")
        cursor.execute(sql, binary=True)
        while True:
            deadline.execute(connection, "SELECT 1")
            batch = cursor.fetchmany(1000)
            deadline.check()
            if not batch:
                return
            for values in batch:
                yield dict(zip(columns, values, strict=True))


def population_summary(orders: Mapping[Any, dict[str, Any]]) -> dict[str, object]:
    eligible = [row for row in orders.values() if row["is_commerce_eligible"]]
    reviews = [row for row in eligible if row["scored_reviews"]]
    weighted = {
        column: str(
            sum((Fraction(row[column], row["scored_reviews"]) for row in reviews), Fraction())
        )
        for column in ("review_score_sum", "low_review_count", "high_review_count")
    }
    return {
        "all_orders": len(orders),
        "delivered_orders": len(eligible),
        "reviewed_delivered_orders": len(reviews),
        "equal_order_review_numerators": weighted,
        "multiple_review_delivered_orders": sum(row["review_count"] > 1 for row in eligible),
        "delivery_eligible": sum(row["is_delivery_eligible"] for row in eligible),
        "promise_eligible": sum(row["is_promise_eligible"] for row in eligible),
        "calendar_late": sum(row["is_calendar_late"] is True for row in eligible),
        "timestamp_late": sum(row["is_timestamp_late"] is True for row in eligible),
        "incomplete_price_orders": sum(not row["is_price_complete"] for row in eligible),
        "incomplete_freight_orders": sum(not row["is_freight_complete"] for row in eligible),
        "incomplete_payment_orders": sum(not row["is_payment_complete"] for row in eligible),
    }


def acceptance_job(settings: Any, folder: Path, deadline: Deadline) -> dict[str, Any]:
    stage = "source"
    try:
        write(folder / "source-started.json", {"stage": stage})
        manifest = verify_raw(ROOT)
        manifest_hash = sha256_file(ROOT / "data/source-manifest.json")
        orders, items, provenance = source_expectations(ROOT)
        deadline.check()
        stage = "before"
        before = metadata(settings, deadline)
        write(folder / "before.json", before)
        comparisons = {}
        types = {}
        with connect(settings, **deadline.connection_options()) as connection:
            with connection.transaction(force_rollback=True):
                deadline.execute(
                    connection, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                for name, expected, keys in (
                    ("mart_order_kpis", orders, ("order_id",)),
                    ("mart_item_kpis", items, ("order_id", "order_item_id")),
                ):
                    stage = name
                    write(folder / (name + "-started.json"), {"stage": stage})
                    started = monotonic()
                    types[name] = verify_types(connection, name, deadline)
                    comparisons[name] = compare_rows(
                        expected, native_rows(connection, name, deadline), keys, deadline
                    )
                    comparisons[name]["elapsed_seconds"] = round(monotonic() - started, 3)
                    write(folder / (name + "-comparison.json"), comparisons[name])
        stage = "after"
        after = metadata(settings, deadline)
        if before["relations"] != after["relations"] or before["raw_bytes"] != after["raw_bytes"]:
            raise ValueError("Read-only acceptance changed warehouse identity")
        if (
            verify_raw(ROOT) != manifest
            or sha256_file(ROOT / "data/source-manifest.json") != manifest_hash
        ):
            raise ValueError("Source changed during native acceptance")
        write(folder / "after.json", after)
        deadline.check()
        return {
            "comparisons": comparisons,
            "native_types": types,
            "source": provenance,
            "population": population_summary(orders),
            "read_only_identity_verified": True,
            "reader_grants_attempted": False,
            "scope": (
                "Current immutable source rows and native types; synthetic native edges, "
                "decimal review diagnostics, consumer query reconciliation and Q01 "
                "are separate gates"
            ),
        }
    except (Exception, KeyboardInterrupt):
        write(folder / "acceptance-failure.json", {"stage": stage, "private_detail_logged": False})
        raise ValueError("Native source acceptance failed; retained evidence only") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-root", type=Path, required=True)
    parser.add_argument("--expected-project-ref", required=True)
    args = parser.parse_args()
    folder = ROOT / ".artifacts/phase-5" / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    try:
        root = _isolated_root(args.settings_root, args.expected_project_ref)
        settings = _settings(root, "admin", args.expected_project_ref)
        result = run_bounded_measurement(acceptance_job, settings, folder)
        receipt = {
            "status": "passed",
            "completed_utc": datetime.now(UTC).isoformat(),
            "project_ref": args.expected_project_ref,
            "result": result,
            "artifacts": str(folder.relative_to(ROOT)),
        }
        write(folder / "acceptance-receipt.json", receipt)
        print(json.dumps(receipt))
        return 0
    except (Exception, KeyboardInterrupt):
        write(
            folder / "failure.json",
            {"status": "failed", "read_only": True, "private_detail_logged": False},
        )
        print(json.dumps({"status": "failed", "artifacts": str(folder.relative_to(ROOT))}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
