"""Exercise actual order projection, domain, lineage and dbt generic SQL offline.

Synthetic bound VALUES remain in an in-memory, query-only SQLite connection.
SQLite shims replace PostgreSQL timestamp casting/calendar validation and regex
operators; accepted timestamps remain canonical strings for comparison. These
checks cannot prove PostgreSQL physical types, planner evaluation or EXCEPT ALL
multiset reconciliation; separate native opt-in tests cover those boundaries.
No fixture files or persistent database resources are created or removed.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
FLAGS = (
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
DATES = COLUMNS[5:]
OPTIONAL_EVENTS = COLUMNS[6:9]
MANDATORY = COLUMNS[:1] + COLUMNS[1:6] + COLUMNS[9:]
LOAD = "11111111-1111-4111-8111-111111111111"


def order(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(
            COLUMNS,
            (
                LOAD,
                1,
                "a" * 32,
                "b" * 32,
                "delivered",
                "2018-01-01 01:02:03",
                "2018-01-02 01:02:03",
                "2018-01-03 01:02:03",
                "2018-01-04 01:02:03",
                "2018-01-05 00:00:00",
            ),
            strict=True,
        )
    )
    assert set(changes) <= set(values)
    values.update(changes)
    return tuple(values.values())


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = environment.from_string(
        (PROJECT / "macros/source_timestamp.sql").read_text("utf-8")
    ).module

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "orders")
        return "synthetic_orders"

    def ref(name: str) -> str:
        assert name == "stg_orders"
        return "synthetic_staged"

    return environment.from_string((PROJECT / relative_path).read_text("utf-8")).render(
        source=source,
        ref=ref,
        config=lambda **_: "",
        commercelens_nullable_timestamp=macros.commercelens_nullable_timestamp,
    )


def model_contract() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((PROJECT / "models/staging/stg_orders.yml").read_text("utf-8"))["models"][
        0
    ]


def render_generic(column: str, name: str) -> str:
    """Render installed dbt generic SQL with arguments from the actual model YAML."""
    jinja2 = pytest.importorskip("jinja2")
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    test_path = Path(spec.origin).parent / "macros/generic_test_sql" / f"{name}.sql"
    tests = next(item for item in model_contract()["columns"] if item["name"] == column)[
        "data_tests"
    ]
    definition = next(
        item for item in tests if item == name or isinstance(item, dict) and name in item
    )
    arguments = definition[name]["arguments"].copy() if isinstance(definition, dict) else {}
    if name == "relationships":
        assert arguments["to"] == "ref('stg_customers')"
        arguments["to"] = "synthetic_customers"
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = environment.from_string(test_path.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(macros, f"default__test_{name}")(
        model="synthetic_staged", column_name=column, **arguments
    )


def sqlite_input_valid(value: str | None, type_name: str) -> int | None:
    """Limited adapter shim; native PostgreSQL is the casting/calendar authority."""
    assert type_name == "timestamp without time zone"
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return 1
    except ValueError:
        return 0


def run_sql(
    rows: list[tuple[object, ...]],
    singular: str | None = None,
    generic: tuple[str, str] | None = None,
    customers: tuple[str | None, ...] = ("b" * 32,),
) -> list[tuple[object, ...]]:
    """Run rendered projection and optional actual test SQL with bound values."""
    assert not (singular and generic)
    projection = render_sql("models/staging/stg_orders.sql")
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    query = (
        render_sql(singular)
        if singular
        else render_generic(*generic)
        if generic
        else "select * from synthetic_staged"
    )
    statement = (
        "with synthetic_orders ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), synthetic_customers (customer_id) as (values "
        + ", ".join("(?)" for _ in customers)
        + "), synthetic_staged as ("
        + projection
        + ") select * from ("
        + query
        + ") as test_result"
    )
    statement = statement.replace(" !~ ", " not regexp ").replace(" ~ ", " regexp ")
    statement = re.sub(
        r"cast\((case\s.*?end) as timestamp without time zone\)",
        r"timestamp_cast(\1)",
        statement,
        flags=re.DOTALL,
    )
    parameters = tuple(value for row in rows for value in row) + customers
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
        connection.create_function("timestamp_cast", 1, lambda value: value)
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
        connection.create_function(
            "regexp",
            2,
            lambda pattern, value: (
                None if value is None else int(re.fullmatch(pattern, value) is not None)
            ),
        )
        connection.execute("pragma query_only = on")
        result = connection.execute(statement, parameters)
        if singular is None and generic is None:
            assert tuple(column[0] for column in result.description) == COLUMNS + FLAGS
        return result.fetchall()
    finally:
        connection.close()


def test_projection_preserves_all_source_events_literal_status_and_lineage() -> None:
    rows = [order(), order(_source_row=2, order_id="c" * 32, order_status="shipped")]
    assert [row[:10] for row in run_sql(rows)] == rows
    assert all(row[10:] == (0,) * 12 for row in run_sql(rows))
    assert run_sql(rows, "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize("missing", ["", None])
@pytest.mark.parametrize("column", OPTIONAL_EVENTS)
def test_optional_absence_is_retained_and_flags_source_and_delivered_missing(
    column: str, missing: object
) -> None:
    source = order(**{column: missing})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    expected_flags = [0] * 12
    expected_flags[OPTIONAL_EVENTS.index(column)] = 1
    expected_flags[OPTIONAL_EVENTS.index(column) + 3] = 1
    assert projected[10:] == tuple(expected_flags)
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize(
    "status",
    ["created", "approved", "invoiced", "processing", "shipped", "unavailable", "canceled"],
)
def test_non_delivered_source_status_does_not_infer_missing_delivery_failure(status: str) -> None:
    source = order(order_status=status, **dict.fromkeys(OPTIONAL_EVENTS, ""))
    projected = run_sql([source])[0]
    assert projected[4] == status
    assert projected[10:] == (1, 1, 1, *(0,) * 9)
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize("column", DATES)
def test_each_nonempty_rejected_date_is_retained_as_null_and_blocks_source_domain(
    column: str,
) -> None:
    source = order(**{column: "bad date"})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    assert projected[10:13] == (0, 0, 0)
    if column in OPTIONAL_EVENTS:
        assert projected[13 + OPTIONAL_EVENTS.index(column)] == 1
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == [(1,)]


@pytest.mark.parametrize(
    "text",
    [
        "now",
        "today",
        "yesterday",
        "infinity",
        "-infinity",
        "2018-1-1 1:2:3",
        "2018-01-01",
        "2018-01-01T01:02:03",
        "2018-01-01 01:02:03.0",
        "2018-01-01 01:02:03Z",
        "2018-01-01 01:02:03+00:00",
        " 2018-01-01 01:02:03",
        "2018-01-01 01:02:03 ",
        "2018-01-01 24:00:00",
        "2018-01-01 23:59:60",
        "2018-01-01 01:60:00",
        "2018-02-29 01:02:03",
        "1900-02-29 01:02:03",
        "2018-04-31 01:02:03",
        "2018-00-01 01:02:03",
        "2018-01-00 01:02:03",
        "２０１８-01-01 01:02:03",
        " \t\n",
        "1000-01-01 00:00:00",
        "2300-01-01 00:00:00",
        "1677-09-21 00:12:43",
        "2262-04-11 23:47:17",
    ],
)
def test_fixed_grammar_calendar_and_ns_domain_reject_invented_or_unrepresentable_dates(
    text: str,
) -> None:
    source = order(order_purchase_timestamp=text)
    assert run_sql([source])[0][5] is None
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == [(1,)]


@pytest.mark.parametrize(
    "text",
    [
        "1677-09-21 00:12:44",
        "2262-04-11 23:47:16",
        "2000-02-29 23:59:59",
        "2024-02-29 00:00:00",
    ],
)
def test_canonical_boundary_and_leap_day_seconds_are_preserved(text: str) -> None:
    source = order(**dict.fromkeys(DATES, text))
    assert run_sql([source])[0][5:10] == (text,) * 5
    assert run_sql([source])[0][10:] == (0,) * 12
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        ((3, 2, 4, 5), (1, 0, 0, 0, 0, 0)),
        ((3, 4, 2, 5), (0, 1, 0, 1, 0, 0)),
        ((3, 4, 5, 2), (0, 0, 1, 0, 1, 1)),
        ((1, 3, 2, 4), (0, 0, 0, 1, 0, 0)),
        ((1, 3, 4, 2), (0, 0, 0, 0, 1, 1)),
        ((1, 2, 4, 3), (0, 0, 0, 0, 0, 1)),
    ],
)
def test_all_six_actual_event_pair_reversals_are_retained_as_warning_flags(
    days: tuple[int, ...], expected: tuple[int, ...]
) -> None:
    source = order(
        **dict(zip(COLUMNS[5:9], (f"2018-01-{day:02} 00:00:00" for day in days), strict=True))
    )
    assert run_sql([source])[0][5:9] == source[5:9]
    assert run_sql([source])[0][16:] == expected
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize("column", COLUMNS[5:9])
def test_reversal_flags_are_false_when_an_operand_is_missing(column: str) -> None:
    assert run_sql([order(**{column: ""})])[0][16:] == (0,) * 6


def test_estimate_is_preserved_without_an_actual_event_sequence_policy() -> None:
    source = order(order_estimated_delivery_date="2017-01-01 00:00:00")
    assert run_sql([source])[0][9:] == (source[9], *(0,) * 12)
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == []


@pytest.mark.parametrize(
    "changes",
    [
        {"order_id": ""},
        {"order_id": None},
        {"order_id": "A" * 32},
        {"customer_id": ""},
        {"customer_id": None},
        {"customer_id": "invalid"},
        {"order_status": ""},
        {"order_status": None},
        {"order_status": " Delivered "},
        {"_source_row": 0},
        {"_source_row": -1},
        {"_source_row": None},
    ],
)
def test_invalid_key_status_or_ordinal_retains_row_and_blocks_domain(
    changes: dict[str, object],
) -> None:
    source = order(**changes)
    assert len(run_sql([source])) == 1
    assert run_sql([source], "tests/stg_orders_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", MANDATORY)
def test_actual_dbt_not_null_fails_each_missing_mandatory_field(column: str) -> None:
    source = order(**{column: None})
    assert run_sql([source], generic=(column, "not_null")) == [(None,)]


def test_duplicate_order_and_lineage_are_retained_for_actual_key_tests() -> None:
    source = order()
    assert len(run_sql([source, source])) == 2
    assert run_sql([source, source], "tests/stg_orders_lineage_unique.sql") == [(1,)]
    assert run_sql([source, source], generic=("order_id", "unique")) == [("a" * 32, 2)]


def test_conflicting_order_keys_at_distinct_lineage_are_not_arbitrarily_selected() -> None:
    rows = [order(), order(_source_row=2, order_status="shipped")]
    assert [row[:10] for row in run_sql(rows)] == rows
    assert run_sql(rows, "tests/stg_orders_lineage_unique.sql") == []
    assert run_sql(rows, generic=("order_id", "unique")) == [("a" * 32, 2)]


def test_source_ordinal_is_unique_per_load_and_customer_reference_can_repeat() -> None:
    rows = [order(), order(_load_id="22222222-2222-4222-8222-222222222222", order_id="c" * 32)]
    assert [row[:10] for row in run_sql(rows)] == rows
    assert run_sql(rows, "tests/stg_orders_lineage_unique.sql") == []
    assert run_sql(rows, generic=("order_id", "unique")) == []
    assert run_sql(rows, generic=("customer_id", "relationships")) == []


def test_actual_customer_relationship_fails_missing_parent_without_dropping_order() -> None:
    source = order(customer_id="c" * 32)
    assert run_sql([source])[0][:10] == source
    assert run_sql([source], generic=("customer_id", "relationships")) == [("c" * 32,)]


def test_exact_status_is_preserved_and_actual_accepted_values_rejects_changed_case() -> None:
    source = order(order_status="Delivered")
    assert run_sql([source])[0][4] == "Delivered"
    assert run_sql([source], generic=("order_status", "accepted_values")) == [("Delivered", 1)]


def test_model_contract_declares_twenty_five_data_tests_and_flags_are_not_null() -> None:
    columns = model_contract()["columns"]
    assert tuple(item["name"] for item in columns) == COLUMNS + FLAGS
    assert sum(len(item.get("data_tests", [])) for item in columns) + 3 == 25
    for flag in FLAGS:
        assert run_sql([order()], generic=(flag, "not_null")) == []
