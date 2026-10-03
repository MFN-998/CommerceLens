"""Opt-in native date dimension checks with bounded read-only typed CTEs.

Actual model/tests and installed YAML-configured dbt macros are rendered. The
independent Python calendar oracle covers all eight source clocks without reading
warehouse records or creating relations. Warning/status flags never select dates.
"""

from __future__ import annotations

import calendar
import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_DATE_DIMENSION_INTEGRATION") != "1",
    reason="Native read-only date dimension SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "calendar_date",
    "calendar_year",
    "calendar_quarter",
    "calendar_month",
    "day_of_month",
    "iso_year",
    "iso_week",
    "iso_day_of_week",
    "is_weekend",
)
TYPES = ("date", *("integer",) * 7, "boolean")
ORDER_CLOCKS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
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
SOURCE_CLOCKS = (
    *("stg_orders." + column for column in ORDER_CLOCKS),
    "stg_order_items.shipping_limit_date",
    "stg_order_reviews.review_creation_date",
    "stg_order_reviews.review_answer_timestamp",
)
EVENTS = (
    (
        datetime(2020, 12, 31, 23, 59, 59),
        datetime(2021, 1, 1, 0, 0, 1),
        datetime(2020, 2, 29, 12),
        datetime(2021, 1, 3, 23, 59, 59),
        datetime(2021, 1, 4),
        datetime(2030, 1, 1),
        datetime(2018, 7, 31, 1),
        datetime(2018, 7, 30, 22),
    ),
    (datetime(2019, 12, 30), None, None, None, None, datetime(2030, 1, 1, 14), None, None),
    (datetime(2020, 12, 31, 1), None, None, None, None, None, None, None),
    (None,) * 8,
)
TARGET_DATE = date(2020, 12, 31)
EXTRA_DATE = date(2100, 1, 1)
SINGULARS = ("date_dimension_domains", "date_dimension_source_reconciliation")


def _oracle(value: date) -> tuple[object, ...]:
    iso_year, iso_week, iso_day = value.isocalendar()
    weekday = calendar.weekday(value.year, value.month, value.day)
    return (
        value,
        value.year,
        (value.month - 1) // 3 + 1,
        value.month,
        value.day,
        iso_year,
        iso_week,
        iso_day,
        weekday in (calendar.SATURDAY, calendar.SUNDAY),
    )


def _expected(events: tuple[tuple[datetime | None, ...], ...]) -> list[tuple[object, ...]]:
    observed = {clock.date() for row in events for clock in row if clock is not None}
    return [_oracle(value) for value in sorted(observed)]


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_orders": "synthetic_orders",
        "stg_order_items": "synthetic_items",
        "stg_order_reviews": "synthetic_reviews",
        "dim_date": "synthetic_projection",
    }[name]


def _render(relative_path: str) -> str:
    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        _environment()
        .from_string((PROJECT / relative_path).read_text("utf-8"))
        .render(ref=_reference, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_sql(column_name: str, name: str) -> str:
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/core/dim_date.yml").read_text("utf-8"))["models"][
        0
    ]
    assert contract["name"] == "dim_date"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(column["name"] for column in contract["columns"]) == COLUMNS
    assert tuple(column["data_type"] for column in contract["columns"]) == TYPES
    column = next(column for column in contract["columns"] if column["name"] == column_name)
    assert name in column["data_tests"]
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name
    ).strip()


def _before(left: datetime | None, right: datetime | None) -> bool:
    return left is not None and right is not None and left < right


def _cte(
    *,
    events: tuple[tuple[datetime | None, ...], ...] = EVENTS,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert len(events) <= 8 and all(len(row) == 8 for row in events)
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    orders, items, reviews = [], [], []
    for index, row in enumerate(events):
        status = ("canceled", "delivered", "unavailable")[index % 3]
        purchase, approved, carrier, customer, estimated, shipping, creation, answer = row
        missing = (approved is None, carrier is None, customer is None)
        flags = (
            *missing,
            *(status == "delivered" and value for value in missing),
            _before(approved, purchase),
            _before(carrier, purchase),
            _before(customer, purchase),
            _before(carrier, approved),
            _before(customer, approved),
            _before(customer, carrier),
        )
        orders.append((status, purchase, approved, carrier, customer, estimated, *flags))
        items.append((shipping,))
        reviews.append((creation, answer, _before(answer, creation)))
    ctes, parameters = [], []
    for name, columns, types, rows in (
        (
            "orders",
            ("order_status", *ORDER_CLOCKS, *ORDER_FLAGS),
            ("text", *("timestamp without time zone",) * 5, *("boolean",) * 12),
            orders,
        ),
        ("items", ("shipping_limit_date",), ("timestamp without time zone",), items),
        (
            "reviews",
            ("review_creation_date", "review_answer_timestamp", "is_answer_before_creation"),
            ("timestamp without time zone", "timestamp without time zone", "boolean"),
            reviews,
        ),
    ):
        assert all(len(row) == len(columns) for row in rows)
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in types) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in types) + " where false"
        ctes.append(
            "synthetic_"
            + name
            + " ("
            + ", ".join(columns)
            + ") as materialized ("
            + selection
            + ")"
        )
    ctes.append("synthetic_actual as (" + _render("models/core/dim_date.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                "case when calendar_date=%s::date then %s::"
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.extend((TARGET_DATE, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += " where calendar_date is distinct from %s::date"
        parameters.append(TARGET_DATE)
    elif mode == "extra":
        selection += " union all select " + ", ".join("%s::" + kind for kind in TYPES)
        parameters.extend(_oracle(EXTRA_DATE))
    elif mode == "duplicate":
        selection += (
            " union all select " + ", ".join(COLUMNS) + " from synthetic_actual "
            "where calendar_date=%s::date"
        )
        parameters.append(TARGET_DATE)
    ctes.append("synthetic_projection as (" + selection + ")")
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only')"
        ).fetchone() == ("commercelens_transformer", "on")
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Date dimension native setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    with transformer_connection.transaction():
        yield


def _query(connection: psycopg.Connection, sql: str, **options: object):
    cte, parameters = _cte(**options)
    return connection.execute(cte + sql, parameters, binary=True)


def _singular(connection: psycopg.Connection, filename: str, **options: object) -> list[tuple]:
    return _query(
        connection,
        "select * from (" + _render("tests/" + filename + ".sql") + ") as checks",
        **options,
    ).fetchall()


def _generic_count(
    connection: psycopg.Connection, column: str, name: str, **options: object
) -> int:
    row = _query(
        connection, "select count(*) from (" + _generic_sql(column, name) + ") as checks", **options
    ).fetchone()
    assert row is not None
    return row[0]


def test_exact_nine_fields_types_calendar_oracle_and_warning_date_retention(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(transformer_connection, "select * from synthetic_actual order by calendar_date")
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == (1082, *(23,) * 7, 16)
    assert result.fetchall() == _expected(EVENTS)


@pytest.mark.parametrize("source_index", range(8), ids=SOURCE_CLOCKS)
def test_each_source_clock_independently_adds_its_nonnull_calendar_date(
    transformer_connection: psycopg.Connection, source_index: int
) -> None:
    row = tuple(
        datetime(2024, 2, 29, 23, 59, 59) if index == source_index else None for index in range(8)
    )
    assert _query(
        transformer_connection, "select * from synthetic_actual", events=(row,)
    ).fetchall() == [_oracle(date(2024, 2, 29))]


@pytest.mark.parametrize("filename", SINGULARS)
def test_actual_singular_contracts_accept_sparse_observed_calendar_and_warning_dates(
    transformer_connection: psycopg.Connection, filename: str
) -> None:
    assert _singular(transformer_connection, filename) == []


def test_same_date_across_source_clocks_rows_and_times_is_deduplicated(
    transformer_connection: psycopg.Connection,
) -> None:
    events = ((datetime(2020, 2, 29),) * 8, (datetime(2020, 2, 29, 23, 59, 59),) * 8)
    assert _query(
        transformer_connection, "select * from synthetic_actual", events=events
    ).fetchall() == [_oracle(date(2020, 2, 29))]


@pytest.mark.parametrize("time_zone", ["UTC", "Pacific/Honolulu"])
def test_calendar_date_does_not_depend_on_session_timezone(
    transformer_connection: psycopg.Connection, time_zone: str
) -> None:
    assert time_zone in {"UTC", "Pacific/Honolulu"}
    transformer_connection.execute("SET LOCAL TIME ZONE '" + time_zone + "'")
    assert _query(
        transformer_connection, "select * from synthetic_actual order by calendar_date"
    ).fetchall() == _expected(EVENTS)


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_yaml_not_null_blocks_each_missing_required_attribute(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    assert _generic_count(transformer_connection, column, "not_null") == 0
    assert _generic_count(transformer_connection, column, "not_null", override=(column, None)) == 1
    assert _singular(transformer_connection, "date_dimension_domains", override=(column, None))


def test_actual_yaml_unique_blocks_duplicate_calendar_date(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _generic_count(transformer_connection, "calendar_date", "unique") == 0
    assert _generic_count(transformer_connection, "calendar_date", "unique", mode="duplicate") == 1


@pytest.mark.parametrize(
    "column,replacement",
    list(zip(COLUMNS, (date(2020, 12, 30), 2021, 3, 11, 30, 2021, 52, 5, True), strict=True)),
)
def test_actual_domains_and_reconciliation_reject_each_inconsistent_calendar_field(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    options = {"override": (column, replacement)}
    assert _singular(transformer_connection, "date_dimension_domains", **options)
    assert _singular(transformer_connection, "date_dimension_source_reconciliation", **options)


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_actual_reconciliation_blocks_missing_extra_or_duplicate_model_rows(
    transformer_connection: psycopg.Connection, mode: str
) -> None:
    assert _singular(transformer_connection, "date_dimension_source_reconciliation", mode=mode)


@pytest.mark.parametrize("events", [(), ((None,) * 8,)], ids=["no-source-rows", "all-null-clocks"])
def test_empty_or_all_null_sources_produce_no_date_and_all_contracts_pass(
    transformer_connection: psycopg.Connection, events: tuple[tuple[datetime | None, ...], ...]
) -> None:
    result = _query(transformer_connection, "select * from synthetic_actual", events=events)
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == (1082, *(23,) * 7, 16)
    assert result.fetchall() == []
    for filename in SINGULARS:
        assert _singular(transformer_connection, filename, events=events) == []
    for column in COLUMNS:
        assert _generic_count(transformer_connection, column, "not_null", events=events) == 0
    assert _generic_count(transformer_connection, "calendar_date", "unique", events=events) == 0
