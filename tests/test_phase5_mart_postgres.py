"""Opt-in native review diagnostics from unchanged mart SQL and synthetic CTEs."""

from __future__ import annotations

import os
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from test_phase5_order_kpis import COLUMNS, order
from test_phase5_query_postgres import connection as connection

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_PHASE5_NATIVE") != "1",
    reason="Phase5 native checks require explicit isolated-target opt-in",
)

COMPONENT_TYPES = (
    "text",
    "text",
    "timestamp",
    "timestamp",
    "timestamp",
    "date",
    "date",
    "bigint",
    "bigint",
    "bigint",
    "numeric",
    "numeric",
    "numeric",
    "bigint",
    "text",
    "boolean",
)


def execute_reviews(connection, groups):
    parameters = []
    components = []
    reviews = []
    for identity, scores in groups.items():
        # Empty independent amount families have no measured sum. Override every
        # portable fixture float; no binary float enters these native inputs.
        row = order(
            identity,
            item_count=0,
            payment_count=0,
            review_count=len(scores),
            source_price_sum=None,
            source_freight_sum=None,
            source_payment_sum=None,
        )
        components.append("(" + ",".join("%s::" + kind for kind in COMPONENT_TYPES) + ")")
        parameters.extend(row[column] for column in COLUMNS)
    for identity, scores in groups.items():
        for score in scores:
            reviews.append("(%s::text,%s::bigint)")
            parameters.extend((identity, score))
    review_cte = (
        "synthetic_reviews(order_id,review_score) as (values " + ",".join(reviews) + ")"
        if reviews
        else "synthetic_reviews as (select NULL::text as order_id, "
        "NULL::bigint as review_score where false)"
    )
    prefix = (
        "with synthetic_components("
        + ",".join(COLUMNS)
        + ") as (values "
        + ",".join(components)
        + "), "
        + review_cte
        + ", synthetic_items as (select NULL::text as order_id, NULL::numeric as price, "
        "NULL::numeric as freight_value where false), "
        "synthetic_payments as (select NULL::text as order_id, "
        "NULL::numeric as payment_value where false), verified as ("
    )
    model = (
        Path(__file__).resolve().parents[1] / "dbt/models/marts/mart_order_kpis.sql"
    ).read_text("utf-8-sig")
    for source, fixture in (
        ("mart_order_components", "synthetic_components"),
        ("fact_order_items", "synthetic_items"),
        ("fact_payments", "synthetic_payments"),
        ("fact_reviews", "synthetic_reviews"),
    ):
        model = model.replace("{{ ref('" + source + "') }}", fixture)
    try:
        cursor = connection.execute(
            prefix + model + ") select * from verified", parameters, binary=True
        )
        names = [column.name for column in cursor.description]
        rows = [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]
    except Exception:
        pytest.fail(
            "Native mart review verification failed; no private detail logged", pytrace=False
        )
    assert len(rows) == len(groups)
    return {row["order_id"]: row for row in rows}


def assert_diagnostic(value, numerator, denominator, rounded):
    assert isinstance(value, Decimal)
    assert abs(Fraction(value) - Fraction(numerator, denominator)) <= Fraction(1, 10**15)
    assert format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), ".6f") == rounded


@pytest.mark.parametrize(
    "scores,score_sum,low,high,score_rounded,low_rounded,high_rounded",
    [
        ([1, 4, 5], 10, 1, 2, "3.333333", "0.333333", "0.666667"),
        ([1, 1, 5], 7, 2, 1, "2.333333", "0.666667", "0.333333"),
    ],
)
def test_native_review_thirds_keep_per_order_numerators_and_diagnostics(
    connection, scores, score_sum, low, high, score_rounded, low_rounded, high_rounded
):
    rows = execute_reviews(connection, {"many": scores, "single": [5]})
    many, single = rows["many"], rows["single"]
    assert many["review_count"] == many["scored_reviews"] == 3
    assert many["review_score_sum"] == score_sum
    assert many["low_review_count"] == low and many["high_review_count"] == high
    assert_diagnostic(many["order_review_score"], score_sum, 3, score_rounded)
    assert_diagnostic(many["order_low_review_fraction"], low, 3, low_rounded)
    assert_diagnostic(many["order_high_review_fraction"], high, 3, high_rounded)
    assert single["review_count"] == single["scored_reviews"] == 1
    assert single["review_score_sum"] == 5
    assert single["low_review_count"] == 0 and single["high_review_count"] == 1
    assert_diagnostic(single["order_review_score"], 5, 1, "5.000000")
    assert_diagnostic(single["order_low_review_fraction"], 0, 1, "0.000000")
    assert_diagnostic(single["order_high_review_fraction"], 1, 1, "1.000000")
    equal_order = (
        Fraction(many["order_review_score"]) + Fraction(single["order_review_score"])
    ) / 2
    assert abs(equal_order - (Fraction(score_sum, 3) + 5) / 2) <= Fraction(1, 10**15)
    assert equal_order != Fraction(score_sum + 5, 4)


def test_native_missing_and_all_null_reviews_keep_null_diagnostics(connection):
    rows = execute_reviews(connection, {"absent": [], "nulls": [None, None]})
    assert rows["absent"]["review_count"] == 0
    assert rows["nulls"]["review_count"] == 2
    for row in rows.values():
        assert row["scored_reviews"] == row["review_score_sum"] == 0
        assert row["low_review_count"] == row["high_review_count"] == 0
        assert row["order_review_score"] is None
        assert row["order_low_review_fraction"] is None
        assert row["order_high_review_fraction"] is None
