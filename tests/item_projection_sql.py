"""Render the shared item projection and independent synthetic source inputs."""

from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
)
ORDER_COLUMNS = ("order_id", "order_status", "_load_id", "_source_row", "order_purchase_timestamp")


def render_item_sql(relative, *, ref=lambda name: name, config=lambda **_: ""):
    jinja = pytest.importorskip("jinja2")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    context = {"ref": ref, "config": config}
    module = environment.from_string(
        (PROJECT / "macros/item_order_projection.sql").read_text("utf-8")
    ).make_module(context)
    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        **context, item_order_projection=module.item_order_projection
    )


def staged_orders(items, statuses):
    # Context is independent fixture data, not derived from the model under test.
    output = []
    for identifier, status in statuses:
        context = next((row for row in items if row["order_id"] == identifier), None)
        output.append(
            (
                identifier,
                status,
                *(
                    context[c] if context is not None else None
                    for c in ("order_load_id", "order_source_row", "order_purchase_timestamp")
                ),
            )
        )
    return output


def independent_items(items, facts):
    # The independent item oracle retains the supplied projected values; absent
    # source parents have NULL lineage/clocks and false warning flags.
    identities = {row[0] for row in facts}
    result = []
    for original in items:
        row = dict(original)
        if row["order_id"] not in identities:
            row.update(
                order_load_id=None,
                order_source_row=None,
                order_purchase_timestamp=None,
                is_shipping_before_purchase=False,
                is_shipping_beyond_365_days=False,
            )
        result.append(row)
    return result
