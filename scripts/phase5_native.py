"""Explicit, bounded Phase5 development verification; fixed private-safe diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from scripts.measure_warehouse_queries import summarize_plan
from src.analytics.access import MARTS, grant_analytics_reader, verify_reader_catalog
from src.analytics.query import MAX_RESPONSE_BYTES, Query, build_query, fetch_metrics
from src.warehouse.config import ROOT, connect
from src.warehouse.dbt_selected import SelectedDbtError, run_dbt_selected
from src.warehouse.reconstruction import _isolated_root, _settings


def write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, default=str) + "\n")


def metadata(settings):
    with connect(settings) as connection, connection.transaction(force_rollback=True):
        connection.execute("SET TRANSACTION READ ONLY")
        size = connection.execute(
            "select pg_database_size(current_database()), "
            "sum(pg_total_relation_size(c.oid)) filter (where n.nspname='raw' "
            "and c.relkind in ('r','p')) from pg_class c join pg_namespace n on "
            "n.oid=c.relnamespace"
        ).fetchone()
        if size is None or size[0] > 400000000 or size[1] > 367000000:
            raise ValueError("Capacity gate failed")
        roles = connection.execute(
            "select "
            "rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolrep"
            "lication,rolbypassrls from pg_roles where rolname='commercelens_"
            "reader'"
        ).fetchone()
        if roles != (False,) * 7:
            raise ValueError("Reader capability changed")
        relations = connection.execute(
            "select "
            "c.relname,c.oid,r.rolname,c.relkind,c.relacl::text,c.reloptions "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace join "
            "pg_roles r on r.oid=c.relowner where n.nspname='marts' order by "
            "c.relname"
        ).fetchall()
        return {
            "database_bytes": size[0],
            "raw_bytes": int(size[1]),
            "reader_attributes_verified": True,
            "relations": relations,
        }


def verify_access(settings):
    with connect(settings) as connection, connection.transaction(force_rollback=True):
        connection.execute("SET TRANSACTION READ ONLY")
        verify_reader_catalog(connection)
        for name in MARTS:
            row = connection.execute(
                "select has_table_privilege('commercelens_reader',%s,'SELECT'), "
                "has_table_privilege('commercelens_reader',%s,'INSERT,UPDATE,DELE"
                "TE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN,SELECT WITH GRANT OPTION"
                "')",
                ("marts." + name, "marts." + name),
            ).fetchone()
            if row != (True, False):
                raise ValueError("Reader capability mismatch")
        for role in ("anon", "authenticated", "service_role", "public"):
            count = connection.execute(
                "select count(*) from pg_namespace n join pg_class c on "
                "c.relnamespace=n.oid where n.nspname in "
                "('raw','staging','core','marts','ops') and c.relkind in "
                "('r','p','v','m','f') and "
                "(has_table_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNC"
                "ATE,REFERENCES,TRIGGER,MAINTAIN') or has_any_column_privilege(%s"
                ",c.oid,'SELECT,INSERT,UPDATE,REFERENCES'))",
                (role, role),
            ).fetchone()
            if count != (0,):
                raise ValueError("Private warehouse exposure mismatch")
        connection.execute("SET LOCAL ROLE commercelens_reader")
        for statement in (
            "select 1 from raw.orders limit 0",
            "select 1 from core.fact_orders limit 0",
            "select 1 from ops.source_loads limit 0",
            "select 1 from staging.stg_orders limit 0",
        ):
            denied = False
            try:
                with connection.transaction():
                    connection.execute(statement)
            except Exception as error:
                denied = getattr(error, "sqlstate", None) == "42501"
            if not denied:
                raise ValueError("Reader denial probe failed")
    return {"select_marts": len(MARTS), "api_public_roles_denied": 4, "native_denial_probes": 4}


def read_query(settings, query) -> tuple[dict[str, Any], dict[str, Any]]:
    with connect(settings) as connection:
        # The existing admin assumes the NOLOGIN reader for development verification.
        connection.execute("SET ROLE commercelens_reader")
        started = perf_counter()
        response = fetch_metrics(connection, query)
        elapsed = perf_counter() - started
    response_rows = response["rows"]
    if not isinstance(response_rows, list):
        raise ValueError("Invalid response shape")
    body = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
    return response, {
        "seconds": round(elapsed, 6),
        "bytes": len(body),
        "rows": len(response_rows),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def cases():
    all_start, all_end = date(2016, 1, 1), date(2019, 1, 1)
    return [
        ("overview_all", Query(all_start, all_end)),
        ("overview_month", Query(date(2018, 1, 1), date(2018, 2, 1))),
        ("months_all", Query(all_start, all_end, group="month")),
        ("days_year", Query(date(2018, 1, 1), date(2019, 1, 1), group="day")),
        ("states_all", Query(all_start, all_end, group="state")),
        ("categories_all", Query(all_start, all_end, group="category")),
        ("sellers_page", Query(all_start, all_end, group="seller")),
        ("products_page", Query(all_start, all_end, group="product")),
        ("category_state", Query(all_start, all_end, category="beleza_saude", state="SP")),
        ("empty", Query(date(2020, 1, 1), date(2020, 2, 1))),
    ]


def measure(settings, folder):
    measurements = []
    started = perf_counter()
    for name, query in cases():
        if perf_counter() - started > 600:
            raise ValueError("Measurement job budget exceeded")
        _, sample = read_query(settings, query)
        sql, parameters = build_query(query)
        with connect(settings) as connection, connection.transaction(force_rollback=True):
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL ROLE commercelens_reader")
            connection.execute("SET LOCAL statement_timeout='55s'")
            plan_row = connection.execute(
                "EXPLAIN (ANALYZE,BUFFERS,TIMING OFF,FORMAT JSON) " + sql, parameters
            ).fetchone()
            block_row = connection.execute("select current_setting('block_size')").fetchone()
            if plan_row is None or block_row is None:
                raise ValueError("Measurement metadata missing")
            plan = plan_row[0][0]
            block_size = int(block_row[0])
            summary = summarize_plan(plan)
        entry = {
            "name": name,
            "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
            **sample,
            "plan": summary,
            "block_size": block_size,
        }
        write(folder / (name + ".json"), entry)
        measurements.append(entry)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(read_query, settings, query) for _, query in cases()[:2]]
        concurrent = [future.result()[1] for future in futures]
    accepted = all(
        row["seconds"] <= 15
        and row["plan"]["execution_ms"] <= 10000
        and row["bytes"] <= MAX_RESPONSE_BYTES
        and (
            row["plan"]["root_buffers"]["Temp Read Blocks"]
            + row["plan"]["root_buffers"]["Temp Written Blocks"]
        )
        * row["block_size"]
        <= 536870912
        for row in measurements
    ) and all(row["seconds"] <= 20 for row in concurrent)
    return {
        "q01": "passed_bounded_development" if accepted else "failed_budget",
        "queries": measurements,
        "concurrency": 2,
        "concurrent": concurrent,
        "budgets": {
            "serial_client_seconds": 15,
            "server_seconds": 10,
            "concurrent_client_seconds": 20,
            "response_bytes": MAX_RESPONSE_BYTES,
            "maximum_rows": 100,
            "plan_temp_traffic_bytes": 536870912,
            "job_seconds": 600,
        },
        "limitations": "Dated small samples, not cold-cache or percentile/SLO/public-load proof",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=(
            "build-order",
            "build-item",
            "test-order",
            "test-item",
            "grant",
            "verify-access",
            "measure",
            "verify-totals",
        ),
    )
    parser.add_argument("--settings-root", type=Path, required=True)
    parser.add_argument("--expected-project-ref", required=True)
    args = parser.parse_args()
    folder = ROOT / ".artifacts/phase-5" / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    stage = "target"
    grant_committed = False
    grant_attempted = False
    build_attempted = False
    build_committed: bool | None = False
    selected_evidence: dict[str, Any] = {}
    try:
        root = _isolated_root(args.settings_root, args.expected_project_ref)
        transformer = _settings(root, "transformer", args.expected_project_ref)
        admin = _settings(root, "admin", args.expected_project_ref)
        before = metadata(admin)
        write(folder / "before.json", before)
        stage = args.operation
        result: dict[str, Any]
        if args.operation.startswith(("build-", "test-")):
            command: Literal["build", "test"] = (
                "build" if args.operation.startswith("build-") else "test"
            )
            select = "mart_order_kpis" if args.operation.endswith("order") else "mart_item_kpis"
            try:
                result = run_dbt_selected(
                    command,
                    select=select,
                    settings_root=root,
                    expected_project_ref=args.expected_project_ref,
                )
            except SelectedDbtError as error:
                selected_evidence = error.evidence
                build_attempted = command == "build" and selected_evidence["live_attempted"]
                build_committed = selected_evidence["build_committed"]
                raise
            build_attempted = command == "build" and result["live_attempted"]
            build_committed = result["build_committed"]
        elif args.operation == "grant":
            grant_attempted = True
            with connect(transformer) as connection:
                with connection.transaction():
                    grant_analytics_reader(connection)
                    verify_reader_catalog(connection)
                grant_committed = True
            result = verify_access(admin)
        elif args.operation == "verify-access":
            result = verify_access(admin)
        elif args.operation == "measure":
            verify_access(admin)
            result = measure(admin, folder)
        else:
            verify_access(admin)
            response, sample = read_query(admin, cases()[0][1])
            row = response["rows"][0]
            if (
                row["orders"] != 96478
                or row["gmv"] != "13221498.11"
                or row["active_customers"] != 93358
            ):
                raise ValueError("Independent historical totals mismatch")
            result = {"historical_orders_gmv_customers": "passed", "sample": sample}
        after = metadata(admin)
        if args.operation in (
            "measure",
            "verify-totals",
            "verify-access",
            "test-order",
            "test-item",
        ):
            if (
                before["relations"] != after["relations"]
                or before["raw_bytes"] != after["raw_bytes"]
            ):
                raise ValueError("Read-only verification changed warehouse identity")
        write(folder / "after.json", after)
        receipt = {
            "status": "failed_budget" if result.get("q01") == "failed_budget" else "passed",
            "operation": args.operation,
            "completed_utc": datetime.now(UTC).isoformat(),
            "project_ref": args.expected_project_ref,
            "result": result,
            "artifacts": str(folder.relative_to(ROOT)),
        }
        write(folder / "receipt.json", receipt)
        print(json.dumps(receipt, default=str))
        return 0 if receipt["status"] == "passed" else 1
    except (Exception, KeyboardInterrupt):
        write(
            folder / "failure.json",
            {
                "status": "failed",
                "stage": stage,
                "private_detail_logged": False,
                "grant_committed": grant_committed,
                "grant_attempted": grant_attempted,
                "build_attempted": build_attempted,
                "build_committed": build_committed,
                "selected_evidence": selected_evidence,
                "recovery": "Inspect grants before retry"
                if grant_attempted
                else "Inspect selected view and retained evidence before retry"
                if build_attempted
                else "No grant attempted",
            },
        )
        print(
            json.dumps(
                {"status": "failed", "stage": stage, "artifacts": str(folder.relative_to(ROOT))}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
