"""Opt-in native full-row reconciliation using typed, read-only synthetic inputs."""

from __future__ import annotations

import os
import re
from decimal import Decimal

import pytest
from test_phase5_item_context import COLUMNS
from test_phase5_item_kpis import ROOT
from test_phase5_item_postgres import ITEM_TYPES, PRODUCT_TYPES, native_item, native_product
from test_phase5_query_postgres import connection as connection

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_PHASE5_NATIVE") != "1",
    reason="Phase5 native checks require explicit isolated-target opt-in",
)
TYPES = {
    **ITEM_TYPES,
    "policy_version": "text",
    "order_status": "text",
    "is_commerce_eligible": "boolean",
    "is_missing_order": "boolean",
    "is_missing_product": "boolean",
    "product_load_id": "uuid",
    "product_source_row": "bigint",
    "product_category_name": "text",
    "product_category_name_english": "text",
    "is_missing_category": "boolean",
    "is_untranslated_category": "boolean",
}


def render(path):
    sql = (ROOT / path).read_text("utf-8")
    sql = re.sub(r"{{ config\(.*?\) }}", "", sql)
    return re.sub(r"{{ ref\('([a-z_]+)'\) }}", r"\1", sql)


def statement(
    *,
    staged=(("a", "delivered"),),
    facts=None,
    items=None,
    products=None,
    null_field=None,
    duplicate=False,
    reconcile=True,
):
    assert tuple(TYPES) == COLUMNS
    assert null_field is None or null_field in TYPES
    items = [native_item()] if items is None else items
    ctes, parameters = [], []
    for name, types, rows in (
        ("fact_order_items", ITEM_TYPES, [tuple(row[c] for c in ITEM_TYPES) for row in items]),
        ("stg_orders", {"order_id": "text", "order_status": "text"}, staged),
        (
            "fact_orders",
            {"order_id": "text", "order_status": "text"},
            staged if facts is None else facts,
        ),
        ("dim_product", PRODUCT_TYPES, [native_product()] if products is None else products),
    ):
        if rows:
            body = "values " + ",".join(
                "(" + ",".join("%s::" + t for t in types.values()) + ")" for _ in rows
            )
            parameters.extend(value for row in rows for value in row)
        else:
            body = "select " + ",".join("NULL::" + t for t in types.values()) + " where false"
        ctes.append(name + "(" + ",".join(types) + ") as (" + body + ")")
    ctes.append("projected as (" + render("dbt/models/marts/mart_item_kpis.sql") + ")")
    fields = ",".join(("NULL::" + TYPES[c] if c == null_field else c) + " as " + c for c in COLUMNS)
    actual = "select " + fields + " from projected"
    if duplicate:
        actual += " union all select * from projected"
    ctes.append("mart_item_kpis as (" + actual + ")")
    query = (
        render("dbt/tests/item_kpis_source_reconciliation.sql")
        if reconcile
        else "select * from mart_item_kpis"
    )
    return "with " + ",".join(ctes) + " select * from (" + query + ") result", parameters


def execute(connection, **kwargs):
    sql, parameters = statement(**kwargs)
    try:
        cursor = connection.execute(sql, parameters, binary=True)
        return cursor.fetchall(), tuple(c.name for c in cursor.description)
    except Exception:
        pytest.fail("Native item reconciliation failed; no private detail logged", pytrace=False)


def test_native_full_projection_and_exact_money(connection):
    rows, names = execute(connection, reconcile=False)
    assert names == COLUMNS and len(rows) == 1
    row = dict(zip(names, rows[0], strict=True))
    assert {c: row[c] for c in ITEM_TYPES} == native_item()
    assert row["price"] == Decimal("9999999999999999.99")
    assert row["product_load_id"] == native_product()[1]
    assert execute(connection)[0] == []


@pytest.mark.parametrize("field", COLUMNS)
def test_native_each_output_field_change_fails_reconciliation(connection, field):
    assert execute(connection, null_field=field)[0] == [(1, 1, 1, 1)]


@pytest.mark.parametrize("status", [None, "delivered", "Delivered", "delivered ", "canceled", ""])
def test_native_literal_nullable_status_matches(connection, status):
    assert execute(connection, staged=(("a", status),), facts=(("a", status),))[0] == []


@pytest.mark.parametrize(
    "staged,facts",
    [
        ((("a", "canceled"),), (("a", "delivered"),)),
        ((), (("a", "delivered"),)),
        ((("a", "delivered"),), ()),
        ((("A", "delivered"),), (("a", "delivered"),)),
    ],
)
def test_native_independent_order_status_and_presence(connection, staged, facts):
    assert execute(connection, staged=staged, facts=facts)[0] == [(1, 1, 1, 1)]


@pytest.mark.parametrize("side", ["staged", "facts", "both"])
def test_native_parent_and_customer_map_multiplicity_rejected(connection, side):
    # Duplicated fact rows represent invalid customer enrichment multiplicity;
    # the unchanged upstream model's own tests establish how those rows arise.
    one = (("a", "delivered"),)
    assert execute(
        connection,
        staged=one * (2 if side in {"staged", "both"} else 1),
        facts=one * (2 if side in {"facts", "both"} else 1),
    )[0]


def test_native_orphans_empty_population_and_duplicate_rows(connection):
    assert (
        execute(connection, staged=(), facts=(), products=[], items=[native_item(price=None)])[0]
        == []
    )
    assert execute(connection, items=[], staged=(), facts=())[0] == []
    assert execute(connection, duplicate=True)[0] == [(1, 2, 0, 1)]
