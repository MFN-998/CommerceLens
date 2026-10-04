"""Opt-in read-only measurement of three reviewed Phase 3 SQL examples.

Run as ``python -m scripts.measure_warehouse_queries --run`` from the repository.
The existing admin assumes the NOLOGIN reader; this is development verification,
not a production consumer or authentication proof. Outputs are retained, not deleted.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from src.warehouse.config import connect, load_settings

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    "order_component_totals",
    "purchase_month_components",
    "purchase_period_status_components",
)
PERIOD = {"start": date(2018, 1, 1), "end": date(2018, 2, 1)}
AMOUNTS = ("source_price_sum", "source_freight_sum", "source_payment_sum")
EXPECTED_TOTALS = {
    "order_count": 99441,
    "item_count": 112650,
    "payment_count": 103886,
    "review_count": 99224,
    "source_price_sum": Decimal("13591643.70"),
    "source_freight_sum": Decimal("2251909.54"),
    "source_payment_sum": Decimal("16008872.12"),
    "orders_without_items": 775,
    "orders_without_payments": 1,
    "orders_without_reviews": 768,
    "orders_with_multiple_reviews": 547,
    "shipping_before_purchase_count": 0,
    "shipping_beyond_365_days_count": 4,
    "zero_installments_count": 2,
    "zero_payment_value_count": 9,
    "undefined_payment_type_count": 3,
    "answer_before_creation_count": 0,
}


def summarize_plan(explanation: dict[str, Any]) -> dict[str, Any]:
    """Return operational statistics only; root buffer counters include children."""
    root = explanation["Plan"]
    nodes: list[dict[str, Any]] = []

    def visit(node: dict[str, Any]) -> None:
        nodes.append(node)
        for child in node.get("Plans", []):
            visit(child)

    visit(root)
    # Worker sort/hash statistics describe separate worker executions, not buffers.
    local_stats = [part for node in nodes for part in (node, *node.get("Workers", []))]
    return {
        "planning_ms": explanation["Planning Time"],
        "execution_ms": explanation["Execution Time"],
        "output_rows": root["Actual Rows"],
        "node_types": dict(sorted(Counter(node["Node Type"] for node in nodes).items())),
        "root_buffers": {
            key: root.get(key, 0)
            for key in (
                "Shared Hit Blocks",
                "Shared Read Blocks",
                "Shared Dirtied Blocks",
                "Shared Written Blocks",
                "Temp Read Blocks",
                "Temp Written Blocks",
            )
        },
        "disk_sort_instances": sum(part.get("Sort Space Type") == "Disk" for part in local_stats),
        "sort_disk_kb": sum(
            part.get("Sort Space Used", 0)
            for part in local_stats
            if part.get("Sort Space Type") == "Disk"
        ),
        "max_hash_batches": max(
            (
                part.get(key, 0)
                for part in local_stats
                for key in ("Hash Batches", "HashAgg Batches")
            ),
            default=0,
        ),
        "hash_disk_kb": sum(part.get("Disk Usage", 0) for part in local_stats),
    }


def _serialize(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError("Unsupported retained operational value")


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=_serialize, indent=2) + "\n", encoding="utf-8")


def _catalog_snapshot(connection: Any) -> tuple[object, ...]:
    row = connection.execute(
        "SELECT c.oid, c.relowner, c.relacl::text, "
        "has_table_privilege('commercelens_reader',c.oid,'SELECT'), "
        "(SELECT coalesce(md5(string_agg(defaclrole::text||'/'||defaclnamespace::text||'/'||"
        "defaclobjtype::text||'/'||defaclacl::text,',' ORDER BY oid)),'empty') "
        "FROM pg_default_acl) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='marts' AND c.relname='mart_order_components'"
    ).fetchone()
    if row is None or row[3] is not True:
        raise ValueError("Approved reader capability is unavailable")
    return row


def _rollup(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    result = {}
    for name in fields:
        observed = [row[name] for row in rows if row[name] is not None]
        result[name] = sum(observed) if observed else (None if name in AMOUNTS else 0)
    return result


def measure() -> dict[str, Any]:
    """Measure fixed SELECTs serially; fail before reporting acceptance on mismatch."""
    scripts = {
        name: (ROOT / "warehouse/queries" / f"{name}.sql").read_text("utf-8") for name in EXAMPLES
    }
    folder = ROOT / ".artifacts/warehouse-queries" / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "complete": False,
        "artifacts": folder.relative_to(ROOT).as_posix(),
        "role": "commercelens_reader",
        "period": PERIOD,
        "method": "one result read and two serial EXPLAIN ANALYZE runs per SELECT; TIMING OFF",
        "queries": [],
    }
    _write(folder / "measurement.json", receipt)
    outputs: dict[str, list[dict[str, Any]]] = {}
    with connect(load_settings(purpose="admin")) as connection:
        if connection.info.get_parameters().get("sslmode") != "verify-full":
            raise ValueError("Verified TLS required")
        with connection.transaction(force_rollback=True):
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            connection.execute("SET LOCAL statement_timeout='55s'")
            connection.execute("SET LOCAL lock_timeout='5s'")
            before = _catalog_snapshot(connection)
            if connection.execute(
                "SELECT session_user,current_user,current_database(), "
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
            ).fetchone() != ("postgres", "postgres", "postgres", True):
                raise ValueError("Unexpected measurement session")
            connection.execute("SET LOCAL ROLE commercelens_reader")
            if connection.execute(
                "SELECT current_user,current_setting('transaction_read_only'),"
                "current_setting('transaction_isolation'),current_setting('statement_timeout')"
            ).fetchone() != ("commercelens_reader", "on", "repeatable read", "55s"):
                raise ValueError("Unexpected effective measurement capability")
            for name, script in scripts.items():
                parameters = PERIOD if name == EXAMPLES[2] else None
                started = perf_counter()
                cursor = connection.execute(script, parameters, binary=True)
                columns = tuple(column.name for column in cursor.description or ())
                rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
                client_ms = (perf_counter() - started) * 1000
                outputs[name] = rows
                samples = []
                for number in (1, 2):
                    plan_started = perf_counter()
                    plan_row = connection.execute(
                        "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON) " + script,
                        parameters,
                    ).fetchone()
                    if plan_row is None:
                        raise ValueError("Measurement plan is missing")
                    plan = plan_row[0]
                    elapsed_ms = (perf_counter() - plan_started) * 1000
                    _write(folder / f"{name}-plan-{number}.json", plan)
                    summary = summarize_plan(plan[0])
                    if summary["output_rows"] != len(rows):
                        raise ValueError("Plan result shape differs from verified result")
                    samples.append(
                        {"run": number, "client_explain_ms": round(elapsed_ms, 3), **summary}
                    )
                receipt["queries"].append(
                    {
                        "name": name,
                        "sql_sha256": hashlib.sha256(script.encode()).hexdigest(),
                        "columns": columns,
                        "result_rows": len(rows),
                        "result_read_client_ms": round(client_ms, 3),
                        "result_sha256": hashlib.sha256(
                            json.dumps(rows, default=_serialize, sort_keys=True).encode()
                        ).hexdigest(),
                        "samples": samples,
                    }
                )
                _write(folder / "measurement.json", receipt)
    totals_rows = outputs[EXAMPLES[0]]
    if len(totals_rows) != 1:
        raise ValueError("Source totals shape changed")
    totals = totals_rows[0]
    if any(totals[name] != value for name, value in EXPECTED_TOTALS.items()):
        raise ValueError("Source totals differ from accepted immutable snapshot")
    fields = tuple(totals)
    months = outputs[EXAMPLES[1]]
    if _rollup(months, fields) != totals:
        raise ValueError("Purchase-month partition does not conserve all aggregates")
    january = [row for row in months if row["purchase_month"] == PERIOD["start"]]
    if _rollup(outputs[EXAMPLES[2]], fields) != _rollup(january, fields):
        raise ValueError("Half-open status partition does not conserve purchase-month aggregates")
    with connect(load_settings(purpose="admin")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        if _catalog_snapshot(connection) != before:
            raise ValueError("Relation identity, owner, ACL or defaults changed during measurement")
        size_row = connection.execute("SELECT pg_database_size(current_database())").fetchone()
        if size_row is None:
            raise ValueError("Measurement storage size is missing")
        size = size_row[0]
        if size >= 400000000:
            raise ValueError("Development storage ceiling exceeded")
    receipt.update(
        {
            "complete": True,
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "source_totals_reconciled": True,
            "all_months_partition_reconciled": True,
            "period_status_partition_reconciled": True,
            "identity_owner_acl_defaults_preserved": True,
            "database_bytes": size,
            "limitations": (
                "serial development samples, not cold-cache, concurrency, SLO or future login proof"
            ),
        }
    )
    _write(folder / "measurement.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["--run"]:
        print("Use --run to opt into bounded read-only query measurements.", file=sys.stderr)
        return 2
    try:
        result = measure()
        print(json.dumps(result, default=_serialize, indent=2))
        return 0
    except KeyboardInterrupt:
        print(
            "Measurement interrupted; preserve partial artifacts and inspect their receipt.",
            file=sys.stderr,
        )
        return 130
    except Exception:  # noqa: BLE001 - fixed message prevents driver/row/credential detail.
        print(
            "Measurement failed; preserve artifacts. No private error detail logged.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
