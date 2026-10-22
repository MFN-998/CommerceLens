"""Execute actual mart SQL over tiny typed CTEs, without writing database state."""

from pathlib import Path

import pytest
from order_component_sql import render_order_model

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {
    "mart_order_kpis": {
        "fact_orders",
        "fact_order_items",
        "fact_payments",
        "fact_reviews",
    },
    "mart_item_kpis": {"fact_order_items", "fact_orders", "dim_product"},
    "mart_order_components": {"fact_orders", "fact_order_items", "fact_payments", "fact_reviews"},
}


def execute_model(connection, name, fixtures, *, upstream=()):
    required = REFERENCES[name] - set(upstream)
    for parent in upstream:
        required = required | REFERENCES[parent]
    assert set(fixtures) == required
    parameters, ctes = [], []

    def render(model_name):
        if model_name in {"mart_order_components", "mart_order_kpis"}:
            return render_order_model(model_name, ref=lambda name: "synthetic_" + name)
        model = (ROOT / "dbt/models/marts" / (model_name + ".sql")).read_text("utf-8-sig")
        for reference in REFERENCES[model_name]:
            tag = "{{ ref('" + reference + "') }}"
            assert tag in model
            model = model.replace(tag, "synthetic_" + reference)
        assert "{{" not in model
        return model

    for reference, (types, rows) in fixtures.items():
        fixture = "synthetic_" + reference
        if rows:
            values = []
            for row in rows:
                assert len(row) == len(types)
                parameters.extend(row)
                values.append("(" + ",".join("%s::" + kind for kind in types.values()) + ")")
            ctes.append(fixture + "(" + ",".join(types) + ") as (values " + ",".join(values) + ")")
        else:
            cells = ["NULL::" + kind + " as " + column for column, kind in types.items()]
            ctes.append(fixture + " as (select " + ",".join(cells) + " where false)")
    for parent in upstream:
        ctes.append("synthetic_" + parent + " as (" + render(parent) + ")")
    sql = "with " + ",".join(ctes) + ", verified as (" + render(name) + ") select * from verified"
    try:
        cursor = connection.execute(sql, parameters, binary=True)
        names = [column.name for column in cursor.description]
        return [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]
    except Exception:
        pytest.fail("Native mart fixture failed; no private detail logged", pytrace=False)
