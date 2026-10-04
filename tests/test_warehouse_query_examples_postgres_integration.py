"""Opt-in native query examples against tiny, bound, read-only mart inputs.

Only the exact approved relation reference is replaced. Independent Python
Decimal/group oracles check all outputs, including empty/null groups and exact
period boundaries. The actual restricted login needs no warehouse capability:
these statements read synthetic CTEs and session metadata, never source records.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, localcontext
from pathlib import Path

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_QUERY_EXAMPLES_INTEGRATION") != "1",
    reason="Native read-only query example checks require explicit opt-in",
)

QUERIES = Path(__file__).resolve().parents[1] / "warehouse/queries"
QUERY_NAMES = (
    "order_component_totals",
    "purchase_month_components",
    "purchase_period_status_components",
)
ORDER_FLAGS = (
    "is_missing_approval",
    "is_missing_carrier_delivery",
    "is_missing_customer_delivery",
    "is_delivered_missing_approval",
    "is_delivered_missing_carrier_delivery",
    "is_delivered_missing_customer_delivery",
    "is_approval_before_purchase",
    "is_carrier_delivery_before_purchase",
    "is_customer_delivery_before_purchase",
    "is_carrier_delivery_before_approval",
    "is_customer_delivery_before_approval",
    "is_customer_delivery_before_carrier_delivery",
)
ORDER_COUNTS = tuple(flag.removeprefix("is_") + "_order_count" for flag in ORDER_FLAGS)
COMPONENT_COLUMNS = (
    "item_count",
    "source_price_sum",
    "source_freight_sum",
    "shipping_before_purchase_count",
    "shipping_beyond_365_days_count",
    "has_items",
    "payment_count",
    "source_payment_sum",
    "zero_installments_count",
    "zero_payment_value_count",
    "undefined_payment_type_count",
    "has_payments",
    "review_count",
    "answer_before_creation_count",
    "has_reviews",
    "has_multiple_reviews",
)
INPUT_COLUMNS = ("order_status", "order_purchase_timestamp", *ORDER_FLAGS, *COMPONENT_COLUMNS)
INPUT_TYPES = (
    "text",
    "timestamp without time zone",
    *("boolean",) * 12,
    "bigint",
    "numeric",
    "numeric",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "numeric",
    "bigint",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "bigint",
    "boolean",
    "boolean",
)
AGGREGATE_COLUMNS = (
    "order_count",
    "item_count",
    "source_price_sum",
    "source_freight_sum",
    "orders_with_items",
    "orders_without_items",
    "shipping_before_purchase_count",
    "shipping_beyond_365_days_count",
    "payment_count",
    "source_payment_sum",
    "orders_with_payments",
    "orders_without_payments",
    "orders_with_measured_zero_payment_sum",
    "zero_installments_count",
    "zero_payment_value_count",
    "undefined_payment_type_count",
    "review_count",
    "orders_with_reviews",
    "orders_without_reviews",
    "orders_with_multiple_reviews",
    "answer_before_creation_count",
    *ORDER_COUNTS,
)
NUMERIC_OUTPUTS = {
    "item_count",
    "source_price_sum",
    "source_freight_sum",
    "shipping_before_purchase_count",
    "shipping_beyond_365_days_count",
    "payment_count",
    "source_payment_sum",
    "zero_installments_count",
    "zero_payment_value_count",
    "undefined_payment_type_count",
    "review_count",
    "answer_before_creation_count",
}
AGGREGATE_TYPES = tuple(1700 if name in NUMERIC_OUTPUTS else 20 for name in AGGREGATE_COLUMNS)
START, END = date(2020, 2, 29), date(2020, 3, 1)
ZERO = Decimal("0.00")
LARGE = Decimal("19999999999999999.98")


@dataclass(frozen=True)
class Components:
    status: str | None = "delivered"
    purchase: datetime | None = datetime(2020, 2, 29, 12)
    items: int = 0
    price: Decimal | None = None
    freight: Decimal | None = None
    shipping_before: int = 0
    shipping_beyond: int = 0
    payments: int = 0
    payment: Decimal | None = None
    zero_installments: int = 0
    zero_values: int = 0
    undefined_types: int = 0
    reviews: int = 0
    answer_before: int = 0
    warnings: tuple[bool, ...] = (False,) * 12


def _warnings(*positions: int) -> tuple[bool, ...]:
    return tuple(index in positions for index in range(12))


RICH = (
    Components(
        purchase=datetime(2020, 2, 29),
        items=2,
        price=Decimal("0.30"),
        freight=Decimal("1.23"),
        shipping_before=1,
        shipping_beyond=1,
        payments=3,
        payment=Decimal("7.01"),
        zero_installments=1,
        zero_values=1,
        undefined_types=1,
        reviews=2,
        answer_before=1,
        warnings=_warnings(0, 3, 6, 9),
    ),
    Components(status="canceled", warnings=_warnings(0, 1, 2)),
    Components(
        status="unavailable",
        purchase=datetime(2020, 3, 1),
        items=1,
        price=ZERO,
        freight=ZERO,
        payments=1,
        payment=ZERO,
        zero_installments=1,
        zero_values=1,
        reviews=1,
    ),
    Components(
        purchase=datetime(2020, 3, 31, 23, 59, 59),
        items=3,
        price=Decimal("10.99"),
        freight=Decimal("0.01"),
        shipping_before=2,
        payments=2,
        payment=Decimal("9.00"),
        zero_values=1,
        reviews=3,
        answer_before=2,
        warnings=_warnings(1, 4, 7, 10, 11),
    ),
    Components(
        status="processing",
        purchase=datetime(2020, 4, 9),
        items=1,
        price=Decimal("9.99"),
        freight=Decimal("2.00"),
        shipping_beyond=1,
        payments=1,
        payment=Decimal("3.21"),
        undefined_types=1,
        warnings=_warnings(2, 5, 8),
    ),
)
MISSING = (
    Components(status="canceled", warnings=(True,) * 12),
    Components(status="processing", purchase=datetime(2020, 3, 1)),
)
MEASURED_ZERO = (
    Components(
        items=1, price=ZERO, freight=ZERO, payments=2, payment=ZERO, zero_values=2, reviews=1
    ),
    Components(status="canceled"),
)
MIXED = (
    Components(),
    Components(items=1, price=Decimal("0.10"), freight=ZERO),
    Components(items=1, price=Decimal("0.20"), freight=Decimal("0.01")),
    Components(payments=2, payment=Decimal("1.01"), zero_values=1),
)
LITERAL_STATUSES = tuple(
    Components(status=status, items=index + 1, price=Decimal(index), freight=ZERO)
    for index, status in enumerate(
        ("delivered", "Delivered", " delivered", "delivered ", "é", "e\u0301", "𐍈🙂", None)
    )
)
NULL_PURCHASE = (
    Components(status="unknown", purchase=None, payments=1, payment=ZERO, zero_values=1),
    Components(status=None, purchase=None, items=1, price=Decimal("0.01"), freight=ZERO),
    Components(items=1, price=Decimal("0.10"), freight=ZERO),
)
BOUNDARIES = (
    Components(status="before", purchase=datetime(2020, 2, 28, 23, 59, 59)),
    Components(status="start", purchase=datetime(2020, 2, 29), payments=1, payment=Decimal("0.10")),
    Components(
        status="inside",
        purchase=datetime(2020, 2, 29, 23, 59, 59),
        payments=1,
        payment=Decimal("0.20"),
    ),
    Components(status="end", purchase=datetime(2020, 3, 1)),
    Components(status="after", purchase=datetime(2020, 3, 1, 0, 0, 1)),
)
LARGE_AMOUNTS = (
    Components(items=2, price=LARGE, freight=LARGE, payments=2, payment=LARGE),
    Components(items=2, price=LARGE, freight=LARGE, payments=2, payment=LARGE),
    Components(items=1, price=Decimal("0.01"), freight=ZERO, payments=1, payment=Decimal("0.01")),
)
MONTH_BOUNDARIES = tuple(
    Components(purchase=clock, reviews=index + 1, answer_before=index)
    for index, clock in enumerate(
        (
            datetime(2020, 2, 28, 23, 59, 59),
            datetime(2020, 2, 29),
            datetime(2020, 2, 29, 23, 59, 59),
            datetime(2020, 3, 1),
            datetime(2020, 12, 31, 23, 59, 59),
            datetime(2021, 1, 1),
        )
    )
)


def _record(row: Components) -> tuple[object, ...]:
    return (
        row.status,
        row.purchase,
        *row.warnings,
        row.items,
        row.price,
        row.freight,
        row.shipping_before,
        row.shipping_beyond,
        row.items > 0,
        row.payments,
        row.payment,
        row.zero_installments,
        row.zero_values,
        row.undefined_types,
        row.payments > 0,
        row.reviews,
        row.answer_before,
        row.reviews > 0,
        row.reviews > 1,
    )


def _source_cte(
    rows: tuple[Components, ...], source_collation: str | None
) -> tuple[str, dict[str, object]]:
    assert source_collation in {None, "POSIX"}
    casts = tuple(
        "::" + kind + (' COLLATE "POSIX"' if kind == "text" and source_collation else "")
        for kind in INPUT_TYPES
    )
    parameters: dict[str, object] = {}
    if rows:
        values = []
        for ordinal, row in enumerate(rows):
            record = _record(row)
            assert len(record) == len(INPUT_COLUMNS) == len(casts)
            placeholders = []
            for index, (value, cast) in enumerate(zip(record, casts, strict=True)):
                key = f"source_{ordinal}_{index}"
                parameters[key] = value
                placeholders.append(f"%({key})s" + cast)
            values.append("(" + ", ".join(placeholders) + ")")
        body = "VALUES " + ", ".join(values)
    else:
        body = "SELECT " + ", ".join("NULL" + cast for cast in casts) + " WHERE false"
    return "WITH example_orders (" + ", ".join(INPUT_COLUMNS) + ") AS (" + body + ")\n", parameters


def _money_sum(values: list[Decimal | None]) -> Decimal | None:
    measured = [value for value in values if value is not None]
    return sum(measured, Decimal(0)) if measured else None


def _aggregates(rows: list[Components]) -> tuple[object, ...]:
    # Python grouping and predicates are independent of the SQL aggregate text.
    with localcontext() as context:
        context.prec = 60
        expected = {
            "order_count": len(rows),
            "item_count": Decimal(sum(row.items for row in rows)),
            "source_price_sum": _money_sum([row.price for row in rows]),
            "source_freight_sum": _money_sum([row.freight for row in rows]),
            "orders_with_items": sum(row.items > 0 for row in rows),
            "orders_without_items": sum(row.items == 0 for row in rows),
            "shipping_before_purchase_count": Decimal(sum(row.shipping_before for row in rows)),
            "shipping_beyond_365_days_count": Decimal(sum(row.shipping_beyond for row in rows)),
            "payment_count": Decimal(sum(row.payments for row in rows)),
            "source_payment_sum": _money_sum([row.payment for row in rows]),
            "orders_with_payments": sum(row.payments > 0 for row in rows),
            "orders_without_payments": sum(row.payments == 0 for row in rows),
            "orders_with_measured_zero_payment_sum": sum(
                row.payments > 0 and row.payment == 0 for row in rows
            ),
            "zero_installments_count": Decimal(sum(row.zero_installments for row in rows)),
            "zero_payment_value_count": Decimal(sum(row.zero_values for row in rows)),
            "undefined_payment_type_count": Decimal(sum(row.undefined_types for row in rows)),
            "review_count": Decimal(sum(row.reviews for row in rows)),
            "orders_with_reviews": sum(row.reviews > 0 for row in rows),
            "orders_without_reviews": sum(row.reviews == 0 for row in rows),
            "orders_with_multiple_reviews": sum(row.reviews > 1 for row in rows),
            "answer_before_creation_count": Decimal(sum(row.answer_before for row in rows)),
        }
        expected.update(
            {
                name: sum(row.warnings[index] for row in rows)
                for index, name in enumerate(ORDER_COUNTS)
            }
        )
        return tuple(expected[name] for name in AGGREGATE_COLUMNS)


def _oracle(
    name: str, rows: tuple[Components, ...], start: date, end: date
) -> Counter[tuple[object, ...]]:
    if name == "order_component_totals":
        return Counter([_aggregates(list(rows))])
    groups: dict[date | str | None, list[Components]] = defaultdict(list)
    lower, upper = datetime.combine(start, time.min), datetime.combine(end, time.min)
    for row in rows:
        if name == "purchase_month_components":
            key = date(row.purchase.year, row.purchase.month, 1) if row.purchase else None
        else:
            if row.purchase is None or not lower <= row.purchase < upper:
                continue
            key = row.status
        groups[key].append(row)
    return Counter((key, *_aggregates(group)) for key, group in groups.items())


def _query(
    connection: psycopg.Connection,
    name: str,
    rows: tuple[Components, ...],
    start: date,
    end: date,
    source_collation: str | None,
) -> psycopg.Cursor:
    assert name in QUERY_NAMES and start < end
    script = (QUERIES / (name + ".sql")).read_text("utf-8")
    assert script.count("marts.mart_order_components") == 1
    script = script.replace("marts.mart_order_components", "example_orders")
    source_sql, source_parameters = _source_cte(rows, source_collation)
    period_parameters = {"start": start, "end": end} if name == QUERY_NAMES[2] else {}
    assert source_parameters.keys().isdisjoint(period_parameters)
    try:
        return connection.execute(
            source_sql + script, source_parameters | period_parameters, binary=True
        )
    except psycopg.Error:
        pytest.fail(
            "Query example native execution failed; no driver detail logged.", pytrace=False
        )


def _assert_metadata(cursor: psycopg.Cursor, name: str) -> None:
    prefix = (
        ()
        if name == QUERY_NAMES[0]
        else (("purchase_month",) if name == QUERY_NAMES[1] else ("order_status",))
    )
    prefix_types = () if not prefix else ((1082,) if name == QUERY_NAMES[1] else (25,))
    assert cursor.description is not None
    assert tuple(column.name for column in cursor.description) == (*prefix, *AGGREGATE_COLUMNS)
    assert tuple(column.type_code for column in cursor.description) == (
        *prefix_types,
        *AGGREGATE_TYPES,
    )
    for column in cursor.description:
        if column.type_code == 1700:
            assert (column.precision, column.scale) == (None, None)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction(force_rollback=True))
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout='55s'")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "current_setting('transaction_read_only'), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == (
            "commercelens_transform",
            "commercelens_transform",
            "postgres",
            "on",
            True,
        )
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Query example native setup failed; inspect private configuration.", pytrace=False
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


@pytest.mark.parametrize(
    ("rows", "start", "end", "timezone", "source_collation"),
    [
        pytest.param(RICH, START, END, "UTC", "POSIX", id="all-statuses-warnings-components"),
        pytest.param((), START, END, "UTC", "POSIX", id="typed-empty-input"),
        pytest.param(MISSING, START, END, "UTC", "POSIX", id="all-families-missing"),
        pytest.param(MEASURED_ZERO, START, END, "UTC", "POSIX", id="measured-zero-versus-missing"),
        pytest.param(MIXED, START, END, "UTC", "POSIX", id="mixed-null-and-exact-cents"),
        pytest.param(LITERAL_STATUSES, START, END, "UTC", "POSIX", id="literal-status-groups"),
        pytest.param(NULL_PURCHASE, START, END, "UTC", "POSIX", id="null-purchase-group-retained"),
        pytest.param(BOUNDARIES, START, END, "UTC", "POSIX", id="half-open-midnight-period"),
        pytest.param(LARGE_AMOUNTS, START, END, "UTC", None, id="unconstrained-numeric-headroom"),
        pytest.param(
            MONTH_BOUNDARIES, date(2020, 2, 1), date(2020, 4, 1), "UTC", None, id="leap-months-utc"
        ),
        pytest.param(
            MONTH_BOUNDARIES,
            date(2020, 2, 1),
            date(2020, 4, 1),
            "Pacific/Honolulu",
            None,
            id="leap-months-honolulu",
        ),
    ],
)
def test_actual_queries_match_all_independent_aggregates_and_native_metadata(
    transformer_connection: psycopg.Connection,
    rows: tuple[Components, ...],
    start: date,
    end: date,
    timezone: str,
    source_collation: str | None,
) -> None:
    connection = transformer_connection
    with connection.transaction():
        try:
            connection.execute("SELECT set_config('TimeZone', %s, true)", (timezone,))
        except psycopg.Error:
            pytest.fail(
                "Query example timezone setup failed; no driver detail logged.", pytrace=False
            )
        for name in QUERY_NAMES:
            cursor = _query(connection, name, rows, start, end, source_collation)
            _assert_metadata(cursor, name)
            assert Counter(cursor.fetchall()) == _oracle(name, rows, start, end)
        try:
            role = connection.execute("SELECT current_user").fetchone()
        except psycopg.Error:
            pytest.fail(
                "Query example session check failed; no driver detail logged.", pytrace=False
            )
        assert role == ("commercelens_transform",)
