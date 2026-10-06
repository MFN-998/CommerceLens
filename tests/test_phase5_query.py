"""Independent query-boundary and exact-response regressions, without a database."""

from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.analytics.query import (
    COUNTS,
    AnalyticsError,
    Query,
    build_query,
    fetch_metrics,
    serialize_row,
)


def request(**changes):
    return Query(date(2020, 2, 29), date(2020, 3, 1), **changes)


def raw(**changes):
    row = {key: 0 for key in COUNTS}
    row.update(
        group_key=None,
        review_bins=[],
        known_gmv=None,
        known_freight_value=None,
        known_payment_value=None,
        delivery_seconds_sum=Decimal(0),
        promise_difference_seconds_sum=Decimal(0),
        total_groups=1,
    )
    row.update(changes)
    return row


def test_empty_population_is_zero_money_and_null_means():
    result = serialize_row(raw(), request())
    assert result["orders"] == 0
    assert result["gmv"] == result["payment_value"] == "0.00"
    assert result["aov"] is result["mean_review_score"] is result["late_delivery_rate"] is None


def test_partial_money_is_known_but_not_complete_and_zero_is_measured():
    result = serialize_row(raw(orders=2, known_gmv=Decimal("0.00"), priced_orders=1), request())
    assert result["known_gmv"] == "0.00"
    assert result["gmv"] is result["aov"] is None
    missing = serialize_row(raw(orders=1, missing_item_orders=1), request())
    assert missing["known_gmv"] is None


def test_exact_large_money_and_half_up_aov():
    result = serialize_row(
        raw(orders=2, priced_orders=2, known_gmv=Decimal("19999999999999999.99")), request()
    )
    assert result["gmv"] == "19999999999999999.99"
    assert result["aov"] == "10000000000000000.00"


def test_review_fractions_combine_exactly_before_rounding():
    # Two orders: scores (1,1,5) and (5); order means 7/3 and5, average11/3.
    result = serialize_row(
        raw(
            orders=2,
            reviewed_orders=2,
            review_pairs=4,
            review_bins=[[3, 7, 2, 1, 1], [1, 5, 0, 1, 1]],
        ),
        request(),
    )
    assert result["mean_review_score"] == "3.666667"
    assert result["low_rating_rate"] == "0.333333"
    assert result["high_rating_rate"] == "0.666667"
    assert result["review_score_weight"] == {"numerator": "22", "denominator": "3"}


def test_item_slices_never_attribute_payments():
    result = serialize_row(raw(orders=1, missing_payment_orders=1), request(group="category"))
    for field in (
        "payment_value",
        "known_payment_value",
        "payment_orders",
        "missing_payment_orders",
        "payment_components",
        "valued_payments",
    ):
        assert result[field] is None


def test_state_concentration_uses_reference_cohort():
    result = serialize_row(
        raw(orders=2, active_customers=2, reference_customers=3), request(state="SP")
    )
    assert result["customer_concentration"] == "0.666667"
    empty = serialize_row(raw(reference_customers=3), request(state="SP"))
    assert empty["customer_concentration"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"group": "source_table"},
        {"limit": True},
        {"limit": 101},
        {"offset": -1},
        {"state": "SP';delete"},
        {"category": "a\x00b"},
        {"category": "x" * 101},
        {"category": "x", "missing_category": True},
        {"seller": "INVALID"},
        {"offset": 1},
    ],
)
def test_reject_unsupported_inputs(changes):
    with pytest.raises(AnalyticsError):
        request(**changes)


def test_reject_timezones_and_bad_periods():
    for start, end in [
        (datetime(2020, 1, 1), date(2020, 2, 1)),
        (date(2020, 1, 1), date(2020, 1, 1)),
        (date(2000, 1, 1), date(2100, 1, 1)),
    ]:
        with pytest.raises(AnalyticsError):
            Query(start, end)


def test_sql_values_are_bound_and_literal_labels_unchanged():
    literal = "x'); SELECT secret FROM raw.orders; --"
    sql, values = build_query(request(group="category", category=literal, state="SP"))
    assert literal not in sql and values["category"] == literal
    assert "%(start)s" in sql and "%(end)s" in sql
    assert 'group by order_id collate "C"' in sql
    assert "limit %(limit)s offset %(offset)s" in sql
    assert "scope as (select * from cohort where customer_state" in sql
    assert "reference_customers from cohort" in sql


@pytest.mark.parametrize(
    "changes",
    [
        {"orders": 9007199254740992},
        {"known_gmv": 0.1},
        {"known_gmv": Decimal("NaN")},
        {"known_gmv": Decimal("0.001")},
        {"late_orders": 1},
        {"active_customers": 1},
        {"reviewed_orders": 1},
        {"review_bins": [[0, 0, 0, 0, 1]]},
        {"review_bins": [[1, 5, 0, 1, 1], [1, 5, 0, 1, 1]]},
        {"review_bins": [[1, 5, 1, 1, 1]]},
    ],
)
def test_fail_closed_for_corrupt_or_unsafe_aggregates(changes):
    with pytest.raises(AnalyticsError):
        serialize_row(raw(**changes), request())


class Connection:
    def __init__(self, rows, identity="commercelens_reader", failure=None):
        self.rows = rows
        self.identity = identity
        self.failure = failure
        self.calls = []
        self.description = [SimpleNamespace(name=name) for name in raw()]

    def transaction(self):
        return nullcontext()

    def execute(self, sql, parameters=None, **kwargs):
        self.calls.append((sql, parameters))
        if parameters is not None and self.failure:
            raise RuntimeError(self.failure)
        return self

    def fetchone(self):
        return (self.identity,)

    def fetchmany(self, size):
        return self.rows[:size]


def test_executor_enforces_identity_limits_and_safe_errors():
    with pytest.raises(AnalyticsError, match="approved reader"):
        fetch_metrics(Connection([], identity="postgres"), request())
    with pytest.raises(AnalyticsError, match="row boundary"):
        fetch_metrics(Connection([tuple(raw().values())] * 2), request(limit=1))
    with pytest.raises(AnalyticsError) as caught:
        fetch_metrics(Connection([], failure="private-driver-secret"), request())
    assert "private-driver-secret" not in str(caught.value)
    connection = Connection([tuple(raw().values())])
    result = fetch_metrics(connection, request())
    assert result["policy_version"] == "v1" and result["rows"][0]["gmv"] == "0.00"
    assert any("statement_timeout='55s'" in sql for sql, _ in connection.calls)


@pytest.mark.parametrize("group", ["day", "month", "category", "seller", "product"])
def test_state_filtered_subgroups_do_not_mislabel_customer_concentration(group):
    result = serialize_row(
        raw(orders=2, active_customers=2, reference_customers=3), request(group=group, state="SP")
    )
    assert result["customer_concentration"] is None
