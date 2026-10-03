"""Execute actual date dimension/test SQL on query-only synthetic SQLite CTEs.

SQL date casts and EXTRACT use a bounded SQLite/date-library adapter; expected
calendar tuples are fixed fixtures, not derived by the adapter. Installed dbt
macros render YAML-configured generics. Occurrence-aware EXCEPT ALL adaptation
tests failure logic; native PostgreSQL remains the physical/date/ISO authority.
No private configuration, network, datasets or persistent fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

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
ORDER_EVENTS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
TABLE_COLUMNS = {
    "orders": (*ORDER_EVENTS, "order_status", "is_customer_delivery_before_purchase"),
    "items": ("shipping_limit_date",),
    "reviews": ("review_creation_date", "review_answer_timestamp", "is_answer_before_creation"),
}
SOURCE_FIELDS = (
    *(("orders", field) for field in ORDER_EVENTS),
    ("items", "shipping_limit_date"),
    ("reviews", "review_creation_date"),
    ("reviews", "review_answer_timestamp"),
)
ORDERS = (
    (
        "2020-02-29 23:59:59",
        "2020-02-29 00:00:00",
        "2021-01-01 12:00:00",
        "2019-12-30 00:01:00",
        "2020-09-30 00:00:00",
        "canceled",
        True,
    ),
    (None, None, None, None, None, "unavailable", False),
    (
        "2000-02-29 12:34:56",
        None,
        "2021-01-03 23:59:59",
        "2021-01-04 00:00:00",
        None,
        "delivered",
        False,
    ),
)
ITEMS = (("2020-04-09 23:59:59",), ("2020-02-29 03:04:05",), (None,))
REVIEWS = (
    ("2020-12-31 14:00:00", "2021-01-01 00:00:00", False),
    ("2021-01-03 23:59:59", "2019-12-30 23:59:59", True),
    (None, None, False),
)
LEAP_DAY = ("2020-02-29", 2020, 1, 2, 29, 2020, 9, 6, True)
EXPECTED = (
    ("2000-02-29", 2000, 1, 2, 29, 2000, 9, 2, False),
    ("2019-12-30", 2019, 4, 12, 30, 2020, 1, 1, False),
    LEAP_DAY,
    ("2020-04-09", 2020, 2, 4, 9, 2020, 15, 4, False),
    ("2020-09-30", 2020, 3, 9, 30, 2020, 40, 3, False),
    ("2020-12-31", 2020, 4, 12, 31, 2020, 53, 4, False),
    ("2021-01-01", 2021, 1, 1, 1, 2020, 53, 5, False),
    ("2021-01-03", 2021, 1, 1, 3, 2020, 53, 7, True),
    ("2021-01-04", 2021, 1, 1, 4, 2021, 1, 1, False),
)


def render(relative: str) -> str:
    jinja = pytest.importorskip("jinja2")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        ref=lambda name: name,
        config=config,
    )


def contract() -> dict:
    return pytest.importorskip("yaml").safe_load(
        (PROJECT / "models/core/dim_date.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str, name: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = dict(definition[name]["arguments"]) if isinstance(definition, dict) else {}
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql" / (name + ".sql")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(module, "default__test_" + name)(
        model="dim_date", column_name=column, **arguments
    )


def sqlite_extract(part: str, value: str | None) -> int | None:
    """Supply only SQL EXTRACT calendar components for synthetic ISO date values."""
    if value is None:
        return None
    observed = date.fromisoformat(value)
    iso = observed.isocalendar()
    return {
        "year": observed.year,
        "quarter": (observed.month - 1) // 3 + 1,
        "month": observed.month,
        "day": observed.day,
        "isoyear": iso.year,
        "week": iso.week,
        "isodow": iso.weekday,
    }[part.lower()]


def sqlite_statement(statement: str) -> str:
    statement = re.sub(
        r"cast\(event_timestamp as date\)",
        "date(event_timestamp)",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(
        r"extract\((year|quarter|month|day|isoyear|week|isodow) from calendar_date\)",
        lambda match: f"calendar_extract('{match[1].lower()}', calendar_date)",
        statement,
        flags=re.IGNORECASE,
    )

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        fields = ", ".join(COLUMNS)
        matches = " and ".join(f"l.{column} is r.{column}" for column in COLUMNS)
        return (
            "select "
            + ", ".join("l." + column for column in COLUMNS)
            + f" from (select *, row_number() over (partition by {fields})"
            + f" as occurrence from {left}) l"
            + f" left join (select *, row_number() over (partition by {fields})"
            + f" as occurrence from {right}) r"
            + f" on {matches} and l.occurrence = r.occurrence where r.occurrence is null"
        )

    return re.sub(
        r"select \* from (expected|actual)\s+except all\s+select \* from (expected|actual)",
        subtract,
        statement,
        flags=re.IGNORECASE,
    )


def run_sql(
    singular: str | None = None,
    generic: tuple[str, str] | None = None,
    *,
    orders: tuple[tuple[object, ...], ...] = ORDERS,
    items: tuple[tuple[object, ...], ...] = ITEMS,
    reviews: tuple[tuple[object, ...], ...] = REVIEWS,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, key, rows in (
        ("stg_orders", "orders", orders),
        ("stg_order_items", "items", items),
        ("stg_order_reviews", "reviews", reviews),
    ):
        columns = TABLE_COLUMNS[key]
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/dim_date.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"dim_date as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(*generic)
        if generic
        else "select * from dim_date"
    )
    statement = sqlite_statement(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    )
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_function("calendar_extract", 2, sqlite_extract)
        connection.execute("pragma query_only=on")
        result = connection.execute(statement, values)
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()


def event_inputs(
    table: str, column: str, *timestamps: str | None
) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Isolate a source column; the other source relations contain no observations."""
    datasets: dict[str, tuple[tuple[object, ...], ...]] = dict.fromkeys(TABLE_COLUMNS, ())
    rows = []
    for timestamp in timestamps:
        values: dict[str, object] = dict.fromkeys(TABLE_COLUMNS[table])
        values[column] = timestamp
        if table == "orders":
            values.update(order_status="canceled", is_customer_delivery_before_purchase=True)
        if table == "reviews":
            values["is_answer_before_creation"] = True
        rows.append(tuple(values[field] for field in TABLE_COLUMNS[table]))
    datasets[table] = tuple(rows)
    return datasets


def test_observed_dates_preserve_warning_events_and_have_fixed_calendar_iso_attributes() -> None:
    assert sorted(run_sql()) == list(EXPECTED)
    assert run_sql("date_dimension_domains") == []
    assert run_sql("date_dimension_source_reconciliation") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
        "date",
        *(["integer"] * 7),
        "boolean",
    ]
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("calendar_date", "unique")) == []


@pytest.mark.parametrize("table,column", SOURCE_FIELDS)
def test_each_source_column_contributes_midnight_and_end_of_day_as_one_date(
    table: str, column: str
) -> None:
    inputs = event_inputs(table, column, "2020-02-29 00:00:00", "2020-02-29 23:59:59", None)
    assert run_sql(**inputs) == [LEAP_DAY]
    assert run_sql("date_dimension_domains", **inputs) == []
    assert run_sql("date_dimension_source_reconciliation", **inputs) == []


@pytest.mark.parametrize(
    "timestamp,calendar_date",
    [
        ("1677-09-21 00:12:44", "1677-09-21"),
        ("2262-04-11 23:47:16", "2262-04-11"),
    ],
)
def test_accepted_source_timestamp_range_endpoints_retain_their_calendar_date(
    timestamp: str, calendar_date: str
) -> None:
    inputs = event_inputs("items", "shipping_limit_date", timestamp)
    result = run_sql(**inputs)
    assert len(result) == 1 and result[0][0] == calendar_date
    assert run_sql("date_dimension_domains", **inputs) == []
    assert run_sql("date_dimension_source_reconciliation", **inputs) == []


def test_repeated_source_observations_do_not_duplicate_the_calendar_grain() -> None:
    inputs = {"orders": ORDERS * 2, "items": ITEMS * 2, "reviews": REVIEWS * 2}
    assert sorted(run_sql(**inputs)) == list(EXPECTED)
    assert run_sql(generic=("calendar_date", "unique"), **inputs) == []
    assert run_sql("date_dimension_source_reconciliation", **inputs) == []


@pytest.mark.parametrize("all_null", [False, True])
def test_empty_or_all_null_event_relations_produce_empty_valid_dimension(all_null: bool) -> None:
    inputs = {
        "orders": ((None, None, None, None, None, "canceled", True),) if all_null else (),
        "items": ((None,),) if all_null else (),
        "reviews": ((None, None, True),) if all_null else (),
    }
    assert run_sql(**inputs) == []
    assert run_sql("date_dimension_domains", **inputs) == []
    assert run_sql("date_dimension_source_reconciliation", **inputs) == []
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null"), **inputs) == []
    assert run_sql(generic=("calendar_date", "unique"), **inputs) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_each_null_output_fails_installed_required_test_and_null_safe_checks(column: str) -> None:
    changes = {column: "null"}
    assert run_sql(generic=(column, "not_null"), changes=changes)
    assert run_sql("date_dimension_domains", changes=changes) == [(len(EXPECTED),)]
    assert run_sql("date_dimension_source_reconciliation", changes=changes) == [
        (len(EXPECTED), len(EXPECTED))
    ]


@pytest.mark.parametrize("column", COLUMNS)
def test_changed_date_or_attribute_fails_consistency_and_full_reconciliation(column: str) -> None:
    expression = (
        "'2001-01-01'"
        if column == "calendar_date"
        else "not is_weekend"
        if column == "is_weekend"
        else column + " + 1"
    )
    changes = {column: expression}
    assert run_sql("date_dimension_domains", changes=changes) == [(len(EXPECTED),)]
    assert run_sql("date_dimension_source_reconciliation", changes=changes) == [
        (len(EXPECTED), len(EXPECTED))
    ]


@pytest.mark.parametrize(
    "corruption,expected,duplicate",
    [
        ({"predicate": "calendar_date <> '2020-04-09'"}, (1, 0), False),
        (
            {"suffix": " union all select '2001-01-01', 2001, 1, 1, 1, 2001, 1, 1, false"},
            (0, 1),
            False,
        ),
        (
            {"suffix": " union all select * from projected where calendar_date = '2020-02-29'"},
            (0, 1),
            True,
        ),
    ],
)
def test_omitted_warning_date_extra_valid_date_or_duplicate_output_fails_membership(
    corruption: dict, expected: tuple[int, int], duplicate: bool
) -> None:
    assert run_sql("date_dimension_domains", **corruption) == []
    assert run_sql("date_dimension_source_reconciliation", **corruption) == [expected]
    assert bool(run_sql(generic=("calendar_date", "unique"), **corruption)) == duplicate
