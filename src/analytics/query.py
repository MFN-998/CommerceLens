"""Bounded Phase 5 query contracts; native/Q01 acceptance gates consumer use.

SQL names come only from fixed maps. Values use driver binding. The caller owns
connection/authentication; this module never loads private settings or creates HTTP routes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Any, Literal

import psycopg

POLICY_VERSION = "v1"
MAX_RESPONSE_BYTES = 524288
MAX_ROWS = 100
MAX_OFFSET = 100000
MAX_PERIOD_DAYS = 3660
SAFE_INTEGER = 9007199254740991
Group = Literal["overview", "day", "month", "state", "category", "seller", "product"]
GROUPS = frozenset({"overview", "day", "month", "state", "category", "seller", "product"})
ITEM_GROUPS = {"category": "product_category_name", "seller": "seller_id", "product": "product_id"}


class AnalyticsError(ValueError):
    """Fixed public-safe diagnostics; never include raw values or driver details."""


@dataclass(frozen=True)
class Query:
    start: date
    end: date
    group: Group = "overview"
    state: str | None = None
    category: str | None = None
    missing_category: bool = False
    seller: str | None = None
    product: str | None = None
    limit: int = MAX_ROWS
    offset: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.start) is not date
            or type(self.end) is not date
            or not 0 < (self.end - self.start).days <= MAX_PERIOD_DAYS
            or not 2000 <= self.start.year <= self.end.year <= 2100
            or not isinstance(self.group, str)
            or self.group not in GROUPS
            or type(self.limit) is not int
            or not 1 <= self.limit <= MAX_ROWS
            or type(self.offset) is not int
            or not 0 <= self.offset <= MAX_OFFSET
            or type(self.missing_category) is not bool
            or (self.category is not None and self.missing_category)
            or (self.group == "overview" and self.offset != 0)
        ):
            raise AnalyticsError("Invalid analytics query boundary")
        if self.state is not None and (
            not isinstance(self.state, str) or re.fullmatch(r"[A-Z]{2}", self.state) is None
        ):
            raise AnalyticsError("Invalid state filter")
        if self.category is not None and (
            not isinstance(self.category, str)
            or not 1 <= len(self.category) <= 100
            or any(ord(char) < 32 for char in self.category)
        ):
            raise AnalyticsError("Invalid category filter")
        for value in (self.seller, self.product):
            if value is not None and (
                not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{32}", value) is None
            ):
                raise AnalyticsError("Invalid item identity filter")

    @property
    def item_scope(self) -> bool:
        return self.group in ITEM_GROUPS or any(
            (
                self.category is not None,
                self.missing_category,
                self.seller is not None,
                self.product is not None,
            )
        )


def build_query(query: Query) -> tuple[str, dict[str, object]]:
    """Return one reviewed SELECT and bound values; no user SQL identifiers."""
    if not isinstance(query, Query):
        raise AnalyticsError("Invalid analytics query")
    parameters: dict[str, object] = {
        "start": query.start,
        "end": query.end,
        "limit": query.limit,
        "offset": query.offset,
    }
    order_filter = (
        "o.is_commerce_eligible and o.order_purchase_timestamp >= %(start)s "
        "and o.order_purchase_timestamp < %(end)s"
    )
    if query.state is not None:
        parameters["state"] = query.state
    groups = {
        "overview": "NULL::text",
        "day": "o.purchase_calendar_date::text",
        "month": "date_trunc('month', o.order_purchase_timestamp)::date::text",
        "state": 'o.customer_state collate "C"',
        "category": "i.group_key",
        "seller": "i.group_key",
        "product": "i.group_key",
    }
    filters = [
        "is_commerce_eligible",
        "order_purchase_timestamp >= %(start)s",
        "order_purchase_timestamp < %(end)s",
    ]
    for attr, column in (
        ("category", "product_category_name"),
        ("seller", "seller_id"),
        ("product", "product_id"),
    ):
        value = getattr(query, attr)
        if value is not None:
            filters.append(f'{column} collate "C" = %({attr})s')
            parameters[attr] = value
    if query.missing_category:
        filters.append("product_category_name is null")
    dimension = ITEM_GROUPS.get(query.group)
    group_key = f'{dimension} collate "C"' if dimension else "NULL::text"
    item_cte = f"""matching_items as (
        select order_id collate "C" as order_id, {group_key} as group_key,
            count(*) as item_count, sum(price) as source_price_sum,
            sum(freight_value) as source_freight_sum,
            count(price) as priced_items, count(freight_value) as freight_items,
            count(*) filter (where is_missing_category) as missing_category_items,
            count(*) filter (where is_untranslated_category) as untranslated_category_items,
            count(price) = count(*) as is_price_complete,
            count(freight_value) = count(*) as is_freight_complete
        from marts.mart_item_kpis where {" and ".join(filters)}
        group by order_id collate "C"{", " + group_key if dimension else ""}
    ), """
    join = ("join" if query.item_scope else "left join") + (
        ' matching_items i on o.order_id collate "C" = i.order_id collate "C"'
    )
    prefix = "i" if query.item_scope else "o"
    item_fields = ", ".join(
        f"{prefix}.{name}"
        for name in (
            "item_count",
            "source_price_sum",
            "source_freight_sum",
            "priced_items",
            "freight_items",
            "is_price_complete",
            "is_freight_complete",
        )
    )
    payment_fields = (
        "o.payment_count, o.valued_payments, o.source_payment_sum, o.is_payment_complete"
    )
    if query.item_scope:
        payment_fields = (
            "0::bigint as payment_count, 0::bigint as valued_payments, "
            "NULL::numeric as source_payment_sum, false as is_payment_complete"
        )
    state_filter = 'where customer_state collate "C" = %(state)s' if query.state is not None else ""
    group_by = "group by group_key" if query.group != "overview" else ""
    group_select = "group_key" if query.group != "overview" else "NULL::text as group_key"
    sql = f"""with {item_cte}cohort as (
        select {groups[query.group]} as group_key, o.customer_unique_id, o.customer_state,
            {item_fields}, {payment_fields},
            coalesce(i.missing_category_items, 0) as missing_category_items,
            coalesce(i.untranslated_category_items, 0) as untranslated_category_items,
            o.order_purchase_timestamp, o.order_delivered_customer_date,
            o.order_estimated_delivery_date, o.review_count, o.scored_reviews,
            o.review_score_sum, o.low_review_count, o.high_review_count,
            o.delivery_seconds, o.promise_difference_seconds,
            o.is_delivery_eligible, o.is_promise_eligible, o.is_calendar_late, o.is_timestamp_late
        from marts.mart_order_kpis o {join} where {order_filter}
    ), scope as (select * from cohort {state_filter}), reference as (
        select count(distinct customer_unique_id collate "C") as reference_customers from cohort
    ), totals as (
        select {group_select}, count(*) as orders,
            count(distinct customer_unique_id collate "C") as active_customers,
            coalesce(sum(item_count), 0) as units,
            coalesce(sum(priced_items), 0) as priced_items,
            coalesce(sum(freight_items), 0) as freight_items,
            coalesce(sum(payment_count), 0) as payment_components,
            coalesce(sum(valued_payments), 0) as valued_payments,
            coalesce(sum(missing_category_items), 0) as missing_category_items,
            coalesce(sum(untranslated_category_items), 0) as untranslated_category_items,
            count(*) filter (where order_delivered_customer_date is null
                or order_purchase_timestamp is null) as missing_delivery_clock_orders,
            count(*) filter (where order_delivered_customer_date < order_purchase_timestamp)
                as reversed_delivery_clock_orders,
            count(*) filter (where is_delivery_eligible and order_estimated_delivery_date is null)
                as missing_promise_clock_orders,
            count(*) filter (where is_delivery_eligible
                and order_estimated_delivery_date < order_purchase_timestamp)
                as reversed_promise_clock_orders,
            sum(source_price_sum) as known_gmv, sum(source_freight_sum) as known_freight_value,
            sum(source_payment_sum) as known_payment_value,
            count(*) filter (where is_price_complete) as priced_orders,
            count(*) filter (where is_freight_complete) as freight_orders,
            count(*) filter (where is_payment_complete) as payment_orders,
            count(*) filter (where item_count = 0) as missing_item_orders,
            count(*) filter (where payment_count = 0) as missing_payment_orders,
            coalesce(sum(review_count), 0) as review_pairs,
            count(*) filter (where review_count > 1) as multiple_review_orders,
            count(*) filter (where scored_reviews > 0) as reviewed_orders,
            count(*) filter (where is_delivery_eligible) as delivery_orders,
            count(*) filter (where is_promise_eligible) as promise_orders,
            count(*) filter (where is_calendar_late) as late_orders,
            count(*) filter (where is_promise_eligible and not is_calendar_late) as on_time_orders,
            count(*) filter (where is_timestamp_late) as timestamp_late_orders,
            coalesce(sum(delivery_seconds), 0) as delivery_seconds_sum,
            coalesce(sum(promise_difference_seconds), 0) as promise_difference_seconds_sum
        from scope {group_by}
    ), bins as (
        select group_key, scored_reviews,
            sum(review_score_sum) as score_sum, sum(low_review_count) as low_count,
            sum(high_review_count) as high_count, count(*) as order_count
        from scope where scored_reviews > 0 group by group_key, scored_reviews
    ), review_weights as (
        select group_key, jsonb_agg(jsonb_build_array(scored_reviews, score_sum,
            low_count, high_count, order_count) order by scored_reviews) as review_bins
        from bins group by group_key
    ) select totals.*, reference.reference_customers,
        coalesce(review_bins, '[]'::jsonb) as review_bins,
        count(*) over () as total_groups
      from totals cross join reference left join review_weights using_dummy on
          totals.group_key is not distinct from using_dummy.group_key
      order by totals.group_key collate "C" nulls first limit %(limit)s offset %(offset)s"""
    return sql, parameters


COUNTS = (
    "orders",
    "active_customers",
    "units",
    "priced_orders",
    "freight_orders",
    "payment_orders",
    "missing_item_orders",
    "missing_payment_orders",
    "review_pairs",
    "multiple_review_orders",
    "reviewed_orders",
    "delivery_orders",
    "promise_orders",
    "late_orders",
    "on_time_orders",
    "timestamp_late_orders",
    "total_groups",
    "reference_customers",
    "priced_items",
    "freight_items",
    "payment_components",
    "valued_payments",
    "missing_category_items",
    "untranslated_category_items",
    "missing_delivery_clock_orders",
    "reversed_delivery_clock_orders",
    "missing_promise_clock_orders",
    "reversed_promise_clock_orders",
)
MONEY = ("known_gmv", "known_freight_value", "known_payment_value")
SECONDS = ("delivery_seconds_sum", "promise_difference_seconds_sum")


def _integer(value: object, *, signed: bool = False) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        result = int(value)
    else:
        raise AnalyticsError("Invalid aggregate count")
    if abs(result) > SAFE_INTEGER or (not signed and result < 0):
        raise AnalyticsError("Aggregate count exceeds response boundary")
    return result


def _money(value: object) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise AnalyticsError("Invalid exact monetary aggregate")
    if isinstance(value.as_tuple().exponent, int) and int(value.as_tuple().exponent) < -2:
        raise AnalyticsError("Unexpected monetary scale")
    if value.adjusted() > 60:
        raise AnalyticsError("Monetary aggregate exceeds response boundary")
    return value


def _decimal(value: Fraction, places: int = 6) -> str:
    with localcontext() as context:
        context.prec = max(80, len(str(abs(value.numerator))) + len(str(value.denominator)) + 10)
        number = Decimal(value.numerator) / Decimal(value.denominator)
        return format(
            number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), f".{places}f"
        )


def _ratio(numerator: int | Fraction, denominator: int, places: int = 6) -> str | None:
    return _decimal(Fraction(numerator) / denominator, places) if denominator else None


def serialize_row(row: dict[str, Any], query: Query) -> dict[str, object]:
    """Serialize approved aggregate fields only; use exact rational review weighting."""
    if set(row) != {"group_key", "review_bins", *COUNTS, *MONEY, *SECONDS}:
        raise AnalyticsError("Unexpected analytics result shape")
    key = row["group_key"]
    if key is not None and (not isinstance(key, str) or len(key) > 100):
        raise AnalyticsError("Invalid analytics grouping value")
    counts = {name: _integer(row[name]) for name in COUNTS}
    money = {name: _money(row[name]) for name in MONEY}
    seconds = {name: _integer(row[name], signed=name.startswith("promise")) for name in SECONDS}
    if (
        any(
            counts[name] > counts["orders"]
            for name in (
                "active_customers",
                "priced_orders",
                "freight_orders",
                "payment_orders",
                "reviewed_orders",
                "multiple_review_orders",
                "missing_item_orders",
                "missing_payment_orders",
                "delivery_orders",
                "promise_orders",
            )
        )
        or counts["late_orders"] + counts["on_time_orders"] != counts["promise_orders"]
    ):
        raise AnalyticsError("Inconsistent analytics coverage")
    totals = [Fraction(0), Fraction(0), Fraction(0)]
    bins = row["review_bins"]
    if not isinstance(bins, list) or len(bins) > 100:
        raise AnalyticsError("Review aggregation exceeds response boundary")
    reviewed = 0
    seen: set[int] = set()
    for bucket in bins:
        if not isinstance(bucket, list) or len(bucket) != 5:
            raise AnalyticsError("Invalid review aggregate")
        size, score, low, high, orders = [_integer(value) for value in bucket]
        if (
            size == 0
            or size in seen
            or orders == 0
            or not size * orders <= score <= 5 * size * orders
            or low + high > size * orders
        ):
            raise AnalyticsError("Inconsistent review aggregate")
        seen.add(size)
        reviewed += orders
        for index, review_value in enumerate((score, low, high)):
            totals[index] += Fraction(review_value, size)
    if reviewed != counts["reviewed_orders"]:
        raise AnalyticsError("Inconsistent reviewed-order coverage")
    result: dict[str, object] = {"group_key": key, **counts, **seconds}
    for name, value in money.items():
        result[name] = (
            format(value, ".2f")
            if value is not None
            else ("0.00" if counts["orders"] == 0 else None)
        )
    for name, known, coverage in (
        ("gmv", "known_gmv", "priced_orders"),
        ("freight_value", "known_freight_value", "freight_orders"),
        ("payment_value", "known_payment_value", "payment_orders"),
    ):
        result[name] = result[known] if counts[coverage] == counts["orders"] else None
    result["customer_concentration"] = (
        _ratio(counts["active_customers"], counts["reference_customers"])
        if counts["orders"]
        and (query.group == "state" or (query.group == "overview" and query.state is not None))
        else None
    )
    result["aov"] = (
        _ratio(Fraction(money["known_gmv"] or 0), counts["orders"], 2)
        if result["gmv"] is not None
        else None
    )
    for name, numerator, denominator in (
        (
            "delivery_days",
            Fraction(seconds["delivery_seconds_sum"], 86400),
            counts["delivery_orders"],
        ),
        (
            "promise_difference_days",
            Fraction(seconds["promise_difference_seconds_sum"], 86400),
            counts["promise_orders"],
        ),
        ("late_delivery_rate", counts["late_orders"], counts["promise_orders"]),
        ("on_time_rate", counts["on_time_orders"], counts["promise_orders"]),
        ("timestamp_late_rate", counts["timestamp_late_orders"], counts["promise_orders"]),
        ("review_coverage", counts["reviewed_orders"], counts["orders"]),
        ("mean_review_score", totals[0], reviewed),
        ("low_rating_rate", totals[1], reviewed),
        ("high_rating_rate", totals[2], reviewed),
    ):
        result[name] = _ratio(numerator, denominator)
    for name, weight in zip(
        ("review_score_weight", "low_review_weight", "high_review_weight"), totals, strict=True
    ):
        result[name] = {"numerator": str(weight.numerator), "denominator": str(weight.denominator)}
    if query.item_scope:
        for name in (
            "payment_orders",
            "missing_payment_orders",
            "known_payment_value",
            "payment_value",
            "payment_components",
            "valued_payments",
        ):
            result[name] = None
    return result


def fetch_metrics(connection: psycopg.Connection, query: Query) -> dict[str, object]:
    """Run a bounded private reader query; caller supplies its authorized connection."""
    sql, parameters = build_query(query)
    try:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout='55s'")
            connection.execute("SET LOCAL lock_timeout='5s'")
            identity = connection.execute("SELECT current_user").fetchone()
            if identity != ("commercelens_reader",):
                raise AnalyticsError("Analytics requires the approved reader capability")
            cursor = connection.execute(sql, parameters, binary=True)
            names = [column.name for column in cursor.description or ()]
            raw = cursor.fetchmany(query.limit + 1)
            if len(raw) > query.limit:
                raise AnalyticsError("Analytics result exceeds row boundary")
            rows = [serialize_row(dict(zip(names, values, strict=True)), query) for values in raw]
        result: dict[str, object] = {
            "policy_version": POLICY_VERSION,
            "currency": "BRL",
            "group": query.group,
            "start": query.start.isoformat(),
            "end_exclusive": query.end.isoformat(),
            "limit": query.limit,
            "offset": query.offset,
            "payment_attributable": not query.item_scope,
            "rows": rows,
        }
        if (
            len(json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode())
            > MAX_RESPONSE_BYTES
        ):
            raise AnalyticsError("Analytics response exceeds byte boundary")
        return result
    except AnalyticsError:
        raise
    except Exception:
        raise AnalyticsError("Analytics query failed; no private detail logged") from None
