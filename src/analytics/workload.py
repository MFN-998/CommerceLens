"""Deterministic Phase 5 cases and private, reproducible measurement provenance.

The returned manifest includes source identities in bound parameters. Callers must
retain it only in ignored private artifacts, never in console output or reports.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from src.analytics.acceptance_source import source_expectations
from src.analytics.query import POLICY_VERSION, Query, build_query

ALL_START, ALL_END = date(2016, 1, 1), date(2019, 1, 1)
YEAR_START = date(2018, 1, 1)


class WorkloadError(ValueError):
    """Fixed diagnostic without source identities or private paths."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _parameters(values: dict[str, object]) -> dict[str, object]:
    return {
        name: value.isoformat() if isinstance(value, date) else value
        for name, value in values.items()
    }


def case_manifest(name: str, query: Query) -> dict[str, object]:
    """Describe the request and effective SQL binding without executing it."""
    sql, parameters = build_query(query)
    canonical_parameters = _parameters(parameters)
    return {
        "name": name,
        "request": _parameters(asdict(query)),
        "parameters": canonical_parameters,
        "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "query_sha256": hashlib.sha256(
            _canonical({"sql": sql, "parameters": canonical_parameters})
        ).hexdigest(),
    }


def source_hashes(root: Path) -> list[dict[str, str]]:
    """Hash the query/oracle/runner and all transitive model and macro sources."""
    paths = {root / "scripts/phase5_native.py"}
    for pattern in ("src/analytics/*.py", "dbt/models/**/*.sql", "dbt/macros/**/*.sql"):
        paths.update(root.glob(pattern))
    try:
        return [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(paths, key=lambda path: path.relative_to(root).as_posix())
        ]
    except OSError:
        raise WorkloadError("Workload source hashing failed") from None


def _eligible(row: dict[str, object], start: date, end: date) -> bool:
    purchase = row["order_purchase_timestamp"]
    return (
        row["is_commerce_eligible"] is True
        and isinstance(purchase, datetime)
        and start <= purchase.date() < end
    )


def _identity_counts(rows: list[dict[str, object]], column: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row[column]
        if not isinstance(value, str) or not value:
            raise WorkloadError("Workload selection identity is invalid")
        counts[value] += 1
    return counts


def _most_frequent(counts: Counter[str]) -> str:
    if not counts:
        raise WorkloadError("Workload has no eligible identity")
    return min(counts, key=lambda identity: (-counts[identity], identity))


def prepare_workload(root: Path) -> tuple[list[tuple[str, Query]], dict[str, object]]:
    """Select representative cases from the checksummed independent source oracle."""
    orders, items, provenance = source_expectations(root)
    eligible_orders = {
        identity: row for identity, row in orders.items() if _eligible(row, ALL_START, ALL_END)
    }
    eligible_items = [
        row
        for (identity, _), row in items.items()
        if identity in eligible_orders and _eligible(row, ALL_START, ALL_END)
    ]
    sellers = _identity_counts(eligible_items, "seller_id")
    products = _identity_counts(eligible_items, "product_id")
    seller, product = _most_frequent(sellers), _most_frequent(products)
    year_days = {
        purchase.date()
        for row in eligible_orders.values()
        if _eligible(row, YEAR_START, ALL_END)
        and isinstance(purchase := row["order_purchase_timestamp"], datetime)
    }
    month_orders = sum(
        _eligible(row, YEAR_START, date(2018, 2, 1)) for row in eligible_orders.values()
    )
    category_state_items = sum(
        row["product_category_name"] == "beleza_saude"
        and eligible_orders[identity]["customer_state"] == "SP"
        for (identity, _), row in items.items()
        if identity in eligible_orders and _eligible(row, ALL_START, ALL_END)
    )
    missing_category_items = sum(row["product_category_name"] is None for row in eligible_items)
    empty_orders = sum(
        _eligible(row, date(2020, 1, 1), date(2020, 2, 1)) for row in orders.values()
    )
    if (
        not month_orders
        or not category_state_items
        or not missing_category_items
        or empty_orders
        or min(len(sellers), len(products), len(year_days)) <= 100
    ):
        raise WorkloadError("Workload source does not support the required representative cases")
    cases = [
        ("overview_all", Query(ALL_START, ALL_END)),
        ("overview_month", Query(YEAR_START, date(2018, 2, 1))),
        ("months_all", Query(ALL_START, ALL_END, group="month")),
        ("days_year", Query(YEAR_START, ALL_END, group="day")),
        ("states_all", Query(ALL_START, ALL_END, group="state")),
        ("categories_all", Query(ALL_START, ALL_END, group="category")),
        ("sellers_page", Query(ALL_START, ALL_END, group="seller")),
        ("products_page", Query(ALL_START, ALL_END, group="product")),
        ("category_state", Query(ALL_START, ALL_END, category="beleza_saude", state="SP")),
        ("empty", Query(date(2020, 1, 1), date(2020, 2, 1))),
        ("seller_filter", Query(ALL_START, ALL_END, seller=seller)),
        ("product_filter", Query(ALL_START, ALL_END, product=product)),
        ("missing_category", Query(ALL_START, ALL_END, missing_category=True)),
        ("sellers_page_2", Query(ALL_START, ALL_END, group="seller", limit=100, offset=100)),
        ("products_page_2", Query(ALL_START, ALL_END, group="product", limit=100, offset=100)),
        ("days_year_page_2", Query(YEAR_START, ALL_END, group="day", limit=100, offset=100)),
    ]
    manifests = []
    for name, query in cases:
        expected = {"rows_min": 1, "rows_max": query.limit if query.group != "overview" else 1}
        if query.group == "overview":
            expected["orders_min"] = 0 if name == "empty" else 1
        if name == "empty":
            expected["orders_max"] = 0
        manifests.append({**case_manifest(name, query), "expected_result": expected})
    return cases, {
        "policy_version": POLICY_VERSION,
        "source": provenance,
        "source_hashes": source_hashes(root),
        "selection": {
            "method": "highest eligible item frequency, lexical identity tie break",
            "eligible_orders": len(eligible_orders),
            "eligible_items": len(eligible_items),
            "distinct_sellers": len(sellers),
            "distinct_products": len(products),
            "seller_item_count": sellers[seller],
            "product_item_count": products[product],
            "year_days": len(year_days),
            "month_orders": month_orders,
            "category_state_items": category_state_items,
            "missing_category_items": missing_category_items,
        },
        "cases": manifests,
    }
