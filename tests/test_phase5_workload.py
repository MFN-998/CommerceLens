"""Synthetic workload selection and provenance checks; no source or native reads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.analytics import workload
from src.analytics.acceptance_source import ItemRows, OrderRows
from src.analytics.query import POLICY_VERSION, Query, build_query


def synthetic_source() -> tuple[OrderRows, ItemRows, dict[str, object]]:
    orders: OrderRows = {}
    items: ItemRows = {}

    def add(index: int, seller: int, product: int, purchase: datetime | None, eligible=True):
        identity = f"order-{index}"
        common = {"is_commerce_eligible": eligible, "order_purchase_timestamp": purchase}
        orders[identity] = {**common, "customer_state": "SP"}
        items[(identity, 1)] = {
            **common,
            "seller_id": f"{seller:032x}",
            "product_id": f"{product:032x}",
            "product_category_name": None if index == 0 else "beleza_saude",
        }

    for index in range(101):
        add(index, index + 1, index + 1, datetime(2018, 1, 1) + timedelta(days=index))
    # Both identities tie at three eligible items. Their order of appearance
    # differs from the lexical winner for products.
    for index in range(101, 105):
        add(index, 1 if index % 2 else 2, 4 if index % 2 else 3, datetime(2018, 1, 1))
    # The most frequent literal identity is ineligible; it must never be selected.
    for index in range(105, 125):
        add(index, 0, 0, datetime(2018, 1, 1), eligible=False)
    for index in range(125, 145):
        add(index, 0, 0, datetime(2015, 12, 31))
    add(145, 0, 0, None)
    return orders, items, {"source_fingerprint": "synthetic", "manifest_sha256": "a" * 64}


@pytest.fixture
def source(monkeypatch):
    result = synthetic_source()
    monkeypatch.setattr(workload, "source_expectations", lambda root: result)
    monkeypatch.setattr(
        workload, "source_hashes", lambda root: [{"path": "synthetic", "sha256": "b"}]
    )
    return result


def test_selects_eligible_frequent_identities_with_stable_lexical_ties(source, monkeypatch):
    cases, manifest = workload.prepare_workload(Path("unused"))
    queries = dict(cases)
    assert queries["seller_filter"].seller == f"{1:032x}"
    assert queries["product_filter"].product == f"{3:032x}"
    assert manifest["selection"] == {
        "method": "highest eligible item frequency, lexical identity tie break",
        "eligible_orders": 105,
        "eligible_items": 105,
        "distinct_sellers": 101,
        "distinct_products": 101,
        "seller_item_count": 3,
        "product_item_count": 3,
        "year_days": 101,
        "month_orders": 35,
        "category_state_items": 104,
        "missing_category_items": 1,
    }
    orders, items, provenance = source
    monkeypatch.setattr(
        workload,
        "source_expectations",
        lambda root: (dict(reversed(orders.items())), dict(reversed(items.items())), provenance),
    )
    assert workload.prepare_workload(Path("unused")) == (cases, manifest)
    assert manifest["source"] == provenance
    assert manifest["policy_version"] == POLICY_VERSION
    assert manifest["source_hashes"] == [{"path": "synthetic", "sha256": "b"}]
    assert f"{1:032x}" not in json.dumps(manifest["selection"])


def test_all_required_case_semantics_and_expected_shapes(source):
    cases, manifest = workload.prepare_workload(Path("unused"))
    queries = dict(cases)
    assert list(queries) == [
        "overview_all",
        "overview_month",
        "months_all",
        "days_year",
        "states_all",
        "categories_all",
        "sellers_page",
        "products_page",
        "category_state",
        "empty",
        "seller_filter",
        "product_filter",
        "missing_category",
        "sellers_page_2",
        "products_page_2",
        "days_year_page_2",
    ]
    assert queries["category_state"].state == "SP"
    assert queries["category_state"].category == "beleza_saude"
    assert queries["missing_category"].missing_category is True
    assert queries["missing_category"].category is None
    assert queries["seller_filter"].item_scope
    assert queries["product_filter"].item_scope
    for page in ("sellers_page_2", "products_page_2", "days_year_page_2"):
        assert queries[page].offset == queries[page].limit == 100
    assert queries["sellers_page_2"].group == "seller"
    assert queries["products_page_2"].group == "product"
    assert queries["days_year_page_2"].group == "day"
    assert queries["days_year_page_2"].start == date(2018, 1, 1)
    for case in manifest["cases"]:
        query = queries[case["name"]]
        expected = case["expected_result"]
        assert expected["rows_min"] == 1
        assert expected["rows_max"] == (1 if query.group == "overview" else 100)
        if case["name"] == "empty":
            assert expected["orders_min"] == expected["orders_max"] == 0
        elif query.group == "overview":
            assert expected["orders_min"] == 1
            assert "orders_max" not in expected
        else:
            assert "orders_min" not in expected


@pytest.mark.parametrize(
    "unsupported",
    [
        "month",
        "category_state",
        "missing_category",
        "seller_page",
        "product_page",
        "day_page",
        "empty",
    ],
)
def test_rejects_sources_that_make_representative_cases_vacuous(source, unsupported):
    orders, items, _ = source
    if unsupported == "month":
        for row in [*orders.values(), *items.values()]:
            if isinstance(row["order_purchase_timestamp"], datetime):
                row["order_purchase_timestamp"] += timedelta(days=31)
    elif unsupported == "category_state":
        for row in orders.values():
            row["customer_state"] = "RJ"
    elif unsupported == "missing_category":
        for row in items.values():
            row["product_category_name"] = "beleza_saude"
    elif unsupported in ("seller_page", "product_page"):
        key = "seller_id" if unsupported == "seller_page" else "product_id"
        for row in items.values():
            row[key] = f"{1:032x}"
    elif unsupported == "day_page":
        for row in [*orders.values(), *items.values()]:
            row["order_purchase_timestamp"] = datetime(2018, 1, 1)
    else:
        orders["unexpected"] = {
            "is_commerce_eligible": True,
            "order_purchase_timestamp": datetime(2020, 1, 1),
        }
    with pytest.raises(workload.WorkloadError, match="required representative cases"):
        workload.prepare_workload(Path("private-path"))


def test_no_eligible_items_fails_without_silently_omitting_identity_filters(source):
    _, items, _ = source
    items.clear()
    with pytest.raises(workload.WorkloadError, match="no eligible identity"):
        workload.prepare_workload(Path("unused"))


def test_selection_requires_an_eligible_existing_parent(source):
    _, items, _ = source
    for index in range(200):
        parent = "order-105" if index % 2 else f"absent-{index}"
        items[(parent, index + 1)] = {
            "is_commerce_eligible": True,
            "order_purchase_timestamp": datetime(2018, 1, 1),
            "seller_id": f"{0:032x}",
            "product_id": f"{0:032x}",
            "product_category_name": "beleza_saude",
        }
    cases, _ = workload.prepare_workload(Path("unused"))
    assert dict(cases)["seller_filter"].seller == f"{1:032x}"


def test_manifest_canonicalizes_complete_request_and_effective_bound_parameters():
    query = Query(date(2018, 1, 1), date(2019, 1, 1), seller="a" * 32, state="SP")
    manifest = workload.case_manifest("private", query)
    sql, parameters = build_query(query)
    expected_request = {**asdict(query), "start": "2018-01-01", "end": "2019-01-01"}
    expected_parameters = {**parameters, "start": "2018-01-01", "end": "2019-01-01"}
    assert manifest["request"] == expected_request
    assert manifest["parameters"] == expected_parameters
    assert manifest["sql_sha256"] == hashlib.sha256(sql.encode()).hexdigest()
    canonical = json.dumps(
        {"sql": sql, "parameters": expected_parameters},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert manifest["query_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert workload.case_manifest("another-name", query)["query_sha256"] == manifest["query_sha256"]
    json.dumps(manifest)


@pytest.mark.parametrize(
    "change",
    [
        {"start": date(2018, 2, 1)},
        {"end": date(2018, 12, 1)},
        {"state": "SP"},
        {"category": "café "},
        {"seller": "a" * 32},
        {"product": "b" * 32},
        {"group": "seller"},
        {"missing_category": True},
        {"limit": 50},
        {"offset": 100},
    ],
)
def test_query_digest_changes_for_every_semantic_request_change(change):
    query = Query(date(2018, 1, 1), date(2019, 1, 1), group="month")
    before = workload.case_manifest("sample", query)
    after = workload.case_manifest("sample", replace(query, **change))
    assert before["query_sha256"] != after["query_sha256"]


def test_same_sql_with_different_identity_bindings_has_distinct_query_digest():
    query = Query(date(2018, 1, 1), date(2019, 1, 1), seller="a" * 32)
    before = workload.case_manifest("sample", query)
    after = workload.case_manifest("sample", replace(query, seller="b" * 32))
    assert before["sql_sha256"] == after["sql_sha256"]
    assert before["query_sha256"] != after["query_sha256"]


def test_effective_sql_changes_are_fingerprinted(monkeypatch):
    query = Query(date(2018, 1, 1), date(2019, 1, 1))
    before = workload.case_manifest("sample", query)
    sql, parameters = build_query(query)
    monkeypatch.setattr(workload, "build_query", lambda query: (sql + "\n", parameters))
    after = workload.case_manifest("sample", query)
    assert before["request"] == after["request"]
    assert before["parameters"] == after["parameters"]
    assert before["sql_sha256"] != after["sql_sha256"]
    assert before["query_sha256"] != after["query_sha256"]


def test_source_hashes_cover_transitive_models_macros_and_python_in_stable_order(tmp_path):
    paths = [
        "src/analytics/query.py",
        "src/analytics/workload.py",
        "scripts/phase5_native.py",
        "dbt/models/staging/orders.sql",
        "dbt/models/marts/kpis.sql",
        "dbt/macros/money.sql",
        "dbt/macros/materializations/view.sql",
    ]
    for name in [*reversed(paths), "dbt/models/marts/kpis.yml", "src/unrelated.py"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    before = workload.source_hashes(tmp_path)
    assert [entry["path"] for entry in before] == sorted(paths)
    assert all(
        entry["sha256"] == hashlib.sha256(entry["path"].encode()).hexdigest() for entry in before
    )
    (tmp_path / "dbt/models/staging/orders.sql").write_text("changed", encoding="utf-8")
    after = workload.source_hashes(tmp_path)
    different = [row["path"] for row, old in zip(after, before, strict=True) if row != old]
    assert different == ["dbt/models/staging/orders.sql"]


def test_missing_required_runner_hash_uses_fixed_diagnostic(tmp_path):
    with pytest.raises(workload.WorkloadError, match="^Workload source hashing failed$"):
        workload.source_hashes(tmp_path)
