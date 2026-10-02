"""Exercise actual item projection, domain, grain, lineage and dbt generic SQL offline.

Bound synthetic VALUES stay in a query-only in-memory SQLite connection. Regex,
calendar and timestamp casting use adapter shims; EXCEPT ALL is adapted through
row-numbered NULL-safe multiset subtraction. SQLite's numeric casting only covers
small synthetic values here: it cannot establish PostgreSQL exact decimal scale,
precision/range, signed-64-bit boundaries or planner safety. Independent native
opt-in tests cover those limits. No files or persistent relations are created.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
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
KEYS = ("order_id", "product_id", "seller_id")
MONEY = ("price", "freight_value")
LOAD = "11111111-1111-4111-8111-111111111111"
PARENTS = {"order_id": "a" * 32, "product_id": "b" * 32, "seller_id": "c" * 32}


def item(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(
            COLUMNS,
            (
                LOAD,
                1,
                PARENTS["order_id"],
                "1",
                PARENTS["product_id"],
                PARENTS["seller_id"],
                "2018-01-02 03:04:05",
                "12.34",
                "5.67",
            ),
            strict=True,
        )
    )
    assert set(changes) <= set(values)
    values.update(changes)
    return tuple(values[column] for column in COLUMNS)


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macro_text = "\n".join(
        (PROJECT / "macros" / name).read_text("utf-8")
        for name in ("source_numeric.sql", "source_timestamp.sql", "source_money.sql")
    )

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_items")
        return "synthetic_order_items"

    def ref(name: str) -> str:
        assert name == "stg_order_items"
        return "synthetic_staged"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        environment.from_string(macro_text + "\n" + (PROJECT / relative_path).read_text("utf-8"))
        .render(source=source, ref=ref, config=config)
        .strip()
    )


def model_contract() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((PROJECT / "models/staging/stg_order_items.yml").read_text("utf-8"))[
        "models"
    ][0]


def render_generic(column: str, name: str) -> str:
    """Render installed dbt generic SQL with the actual item YAML arguments."""
    jinja2 = pytest.importorskip("jinja2")
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    path = Path(spec.origin).parent / "macros/generic_test_sql" / f"{name}.sql"
    tests = next(record for record in model_contract()["columns"] if record["name"] == column)[
        "data_tests"
    ]
    definition = next(
        record for record in tests if record == name or isinstance(record, dict) and name in record
    )
    arguments = definition[name]["arguments"].copy() if isinstance(definition, dict) else {}
    if name == "relationships":
        parent = {"order_id": "orders", "product_id": "products", "seller_id": "sellers"}[column]
        assert arguments == {"to": f"ref('stg_{parent}')", "field": column}
        arguments["to"] = "synthetic_" + parent
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = environment.from_string(path.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(macros, f"default__test_{name}")(
        model="synthetic_staged", column_name=column, **arguments
    )


def sqlite_input_valid(value: str | None, type_name: str) -> int | None:
    """Limited input adapter; native PostgreSQL remains the type authority."""
    if value is None:
        return None
    try:
        if type_name == "timestamp without time zone":
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return 1
        assert type_name == "numeric"
        number = Decimal(value)
        return int(number.is_finite() and (-16383 <= number.adjusted() <= 131071 or number == 0))
    except (InvalidOperation, ValueError, OverflowError):
        return 0


def sqlite_except_all(statement: str) -> str:
    """Adapter-only equivalent of the two actual EXCEPT ALL query operands."""

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        partition = ", ".join(COLUMNS)
        matches = " and ".join(f"lhs.{column} is rhs.{column}" for column in COLUMNS)
        return (
            "select "
            + ", ".join("lhs." + column for column in COLUMNS)
            + " from (select *, row_number() over (partition by "
            + partition
            + ") as occurrence from "
            + left
            + ") lhs left join "
            + "(select *, row_number() over (partition by "
            + partition
            + ") as occurrence from "
            + right
            + ") rhs on "
            + matches
            + " and lhs.occurrence=rhs.occurrence where rhs.occurrence is null"
        )

    return re.sub(
        r"select \* from (expected|actual)\s+except all\s+select \* from (expected|actual)",
        subtract,
        statement,
        flags=re.IGNORECASE,
    )


def run_sql(
    rows: list[tuple[object, ...]],
    singular: str | None = None,
    generic: tuple[str, str] | None = None,
    *,
    changes: dict[str, str] | None = None,
    staged_filter: str = "true",
    staged_suffix: str = "",
    parent_ids: dict[str, str | None] | None = None,
) -> list[tuple[object, ...]]:
    """Run actual model/test SQL with bound raw values and optional staged damage."""
    assert not (singular and generic)
    assert rows
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    parents = PARENTS | (parent_ids or {})
    projection = render_sql("models/staging/stg_order_items.sql")
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    query = (
        render_sql(singular)
        if singular
        else render_generic(*generic)
        if generic
        else "select * from synthetic_staged"
    )
    fields = ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
    statement = (
        "with synthetic_order_items ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), synthetic_orders (order_id) as (values (?)), "
        + "synthetic_products (product_id) as (values (?)), "
        + "synthetic_sellers (seller_id) as (values (?)), projected as ("
        + projection
        + "), synthetic_staged as (select "
        + fields
        + " from projected where "
        + staged_filter
        + staged_suffix
        + ") select * from ("
        + query
        + ") as test_result"
    )
    statement = statement.replace(" !~ ", " not regexp ").replace(" ~ ", " regexp ")
    statement = re.sub(
        r"cast\((case(?:(?!\bcast\s*\().)*?end) as timestamp without time zone\)",
        r"timestamp_cast(\1)",
        statement,
        flags=re.DOTALL,
    )
    # SQLite numeric retains only small-value behavior; native tests establish
    # the actual constrained numeric cast and independently exact boundaries.
    statement = statement.replace("as numeric(18,2)", "as numeric")
    statement = sqlite_except_all(statement)
    parameters = tuple(value for row in rows for value in row) + tuple(parents[key] for key in KEYS)
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
        connection.create_function("timestamp_cast", 1, lambda value: value)
        connection.create_function("trunc", 1, lambda value: None if value is None else int(value))
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
        connection.create_function(
            "regexp",
            2,
            lambda pattern, value: (
                None
                if value is None
                else int(re.fullmatch(pattern.replace("[[:space:]]", r"\s"), value) is not None)
            ),
        )
        connection.execute("pragma query_only = on")
        result = connection.execute(statement, parameters)
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()
    finally:
        connection.close()


def test_literal_ids_lineage_and_all_attributes_preserve_rows_without_parent_join() -> None:
    rows = [item(), item(_source_row=2, order_item_id="2", order_id="d" * 32)]
    projected = run_sql(rows, parent_ids={"order_id": None, "product_id": None, "seller_id": None})
    assert len(projected) == len(rows)
    for source, staged in zip(rows, projected, strict=True):
        assert staged[:3] == source[:3]
        assert staged[3] == int(source[3])
        assert staged[4:7] == source[4:7]
        assert tuple(Decimal(str(value)) for value in staged[7:]) == tuple(
            Decimal(value) for value in source[7:]
        )
    assert run_sql(rows, "tests/stg_order_items_source_reconciliation.sql") == []


@pytest.mark.parametrize("column", MONEY)
@pytest.mark.parametrize("text", ["0", "0.0", "0.00", "000.10", "12", "12.3", "12.34"])
def test_money_grammar_and_zero_preserve_small_exact_source_values(column: str, text: str) -> None:
    source = item(**{column: text})
    assert Decimal(str(run_sql([source])[0][COLUMNS.index(column)])) == Decimal(text)
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == []


@pytest.mark.parametrize("column", MONEY)
@pytest.mark.parametrize(
    "text",
    [
        "-1",
        "+1",
        "1e2",
        "1E-2",
        " 1",
        "1 ",
        "1\n",
        " \t\n",
        ".5",
        "1.",
        "1.230",
        "1.000",
        "1.234",
        "1,00",
        "1_000",
        "NaN",
        "Infinity",
        "１２.３４",
    ],
)
def test_money_rejected_nonempty_grammar_becomes_null_and_blocks_without_rounding(
    column: str,
    text: str,
) -> None:
    source = item(**{column: text})
    projected = run_sql([source])
    assert len(projected) == 1
    assert projected[0][COLUMNS.index(column)] is None
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", COLUMNS[2:])
@pytest.mark.parametrize("missing", ["", None])
def test_mandatory_empty_and_null_values_retain_rows_and_block(
    column: str, missing: object
) -> None:
    source = item(**{column: missing})
    assert run_sql([source])[0][COLUMNS.index(column)] is None
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_dbt_null_test_blocks_every_missing_mandatory_column(column: str) -> None:
    assert run_sql([item(**{column: None})], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("column", KEYS)
@pytest.mark.parametrize("text", ["A" * 32, "short", " " + "a" * 32, "g" * 32])
def test_invalid_literal_key_format_is_preserved_and_blocks(column: str, text: str) -> None:
    source = item(**{column: text})
    assert run_sql([source])[0][COLUMNS.index(column)] == text
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", KEYS)
def test_actual_dbt_relationship_fails_missing_staged_parent_without_removing_item(
    column: str,
) -> None:
    source = item(**{column: "d" * 32})
    assert run_sql([source])[0][COLUMNS.index(column)] == "d" * 32
    assert run_sql([source], generic=(column, "relationships")) == [("d" * 32,)]
    assert run_sql([item()], generic=(column, "relationships")) == []


@pytest.mark.parametrize("text,expected", [("12.0", 12), ("1.2e1", 12), (" \t+12.000\n", 12)])
def test_positive_sequence_uses_existing_integral_decimal_parser(text: str, expected: int) -> None:
    source = item(order_item_id=text)
    assert run_sql([source])[0][3] == expected
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == []


@pytest.mark.parametrize("text,expected", [("0", 0), ("-1", -1), ("1.5", None), ("bad", None)])
def test_nonpositive_or_invalid_sequence_remains_queryable_and_blocks(
    text: str, expected: object
) -> None:
    source = item(order_item_id=text)
    assert run_sql([source])[0][3] == expected
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("ordinal", [None, 0, -1])
def test_source_ordinal_must_be_positive(ordinal: object) -> None:
    source = item(_source_row=ordinal)
    assert run_sql([source])[0][1] == ordinal
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


@pytest.mark.parametrize(
    "text",
    ["1677-09-21 00:12:44", "2262-04-11 23:47:16", "2000-02-29 23:59:59"],
)
def test_shipping_canonical_calendar_and_phase2_boundaries_are_retained(text: str) -> None:
    source = item(shipping_limit_date=text)
    assert run_sql([source])[0][6] == text
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == []


@pytest.mark.parametrize(
    "text",
    [
        "bad",
        "2018-02-29 03:04:05",
        "2018-01-01 24:00:00",
        "2018-01-01 23:59:60",
        "2018-1-1 1:2:3",
        "2018-01-01T03:04:05",
        "2018-01-01 03:04:05.0",
        "2018-01-01 03:04:05Z",
        "2018-01-01 03:04:05+00:00",
        "now",
        "infinity",
        "1677-09-21 00:12:43",
        "2262-04-11 23:47:17",
    ],
)
def test_shipping_invalid_format_calendar_timezone_and_range_becomes_null(text: str) -> None:
    source = item(shipping_limit_date=text)
    assert run_sql([source])[0][6] is None
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


def test_items_with_repeated_individual_keys_satisfy_composite_grain() -> None:
    rows = [item(), item(_source_row=2, order_item_id="2"), item(_source_row=3, order_id="d" * 32)]
    assert len(run_sql(rows)) == 3
    assert run_sql(rows, "tests/stg_order_items_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_items_lineage_unique.sql") == []


def test_duplicate_composite_key_at_distinct_lineage_retains_both_and_blocks_grain() -> None:
    rows = [item(), item(_source_row=2, freight_value="9.99")]
    assert len(run_sql(rows)) == 2
    assert run_sql(rows, "tests/stg_order_items_grain.sql") == [(1,)]
    assert run_sql(rows, "tests/stg_order_items_lineage_unique.sql") == []


def test_duplicate_lineage_at_distinct_item_key_blocks_lineage_only() -> None:
    rows = [item(), item(order_item_id="2")]
    assert run_sql(rows, "tests/stg_order_items_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_items_lineage_unique.sql") == [(1,)]


def test_same_ordinal_in_distinct_loads_satisfies_lineage_uniqueness() -> None:
    rows = [item(), item(_load_id="22222222-2222-4222-8222-222222222222", order_id="d" * 32)]
    assert run_sql(rows, "tests/stg_order_items_lineage_unique.sql") == []


@pytest.mark.parametrize(
    "column,expression",
    [
        ("_load_id", "'22222222-2222-4222-8222-222222222222'"),
        ("_source_row", "_source_row+1"),
        ("order_id", "'" + "d" * 32 + "'"),
        ("order_item_id", "order_item_id+1"),
        ("product_id", "'" + "d" * 32 + "'"),
        ("seller_id", "'" + "d" * 32 + "'"),
        ("shipping_limit_date", "'2018-01-03 03:04:05'"),
        ("price", "price+0.01"),
        ("freight_value", "freight_value+0.01"),
    ],
)
def test_complete_row_multiset_reconciliation_detects_each_count_preserving_change(
    column: str,
    expression: str,
) -> None:
    assert run_sql(
        [item()], "tests/stg_order_items_source_reconciliation.sql", changes={column: expression}
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_dropped_row_and_extra_duplicate() -> None:
    rows = [item(), item(_source_row=2, order_item_id="2")]
    assert run_sql(
        rows, "tests/stg_order_items_source_reconciliation.sql", staged_filter="_source_row<>1"
    ) == [("missing_from_staging", 1)]
    assert run_sql(
        rows,
        "tests/stg_order_items_source_reconciliation.sql",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_same_count_duplicate_substitution() -> None:
    rows = [item(), item(_source_row=2, order_item_id="2")]
    assert run_sql(
        rows,
        "tests/stg_order_items_source_reconciliation.sql",
        staged_filter="_source_row=1",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_rejected_values_reconcile_as_null_but_source_domains_still_block() -> None:
    source = item(price="1.234", shipping_limit_date="bad")
    assert run_sql([source], "tests/stg_order_items_source_reconciliation.sql") == []
    assert run_sql([source], "tests/stg_order_items_source_domains.sql") == [(1,)]


def test_model_contract_declares_exact_types_and_sixteen_blocking_data_tests() -> None:
    contract = model_contract()
    assert contract["config"] == {"materialized": "view", "schema": "staging"}
    columns = contract["columns"]
    assert tuple(record["name"] for record in columns) == COLUMNS
    assert tuple(record["data_type"] for record in columns) == (
        "uuid",
        "bigint",
        "text",
        "bigint",
        "text",
        "text",
        "timestamp without time zone",
        "numeric(18,2)",
        "numeric(18,2)",
    )
    assert sum(len(record["data_tests"]) for record in columns) + 4 == 16
    assert all("not_null" in record["data_tests"] for record in columns)
