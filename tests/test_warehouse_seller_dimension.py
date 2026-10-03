"""Execute actual seller dimension/test SQL with query-only synthetic SQLite inputs.

Native PostgreSQL checks remain authoritative for physical types and collation.
No private configuration, network, datasets or persistent fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = "11111111-1111-4111-8111-111111111111"
COLUMNS = (
    "_load_id",
    "_source_row",
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
    "has_geolocation",
)
SELLERS = (
    (LOAD, 1, "a" * 32, "00123", " São Paulo🙂 ", "SP"),
    (LOAD, 2, "b" * 32, "00123", "são paulo", "RJ"),
    (LOAD, 3, "c" * 32, "2", "Café d'Água", "AM"),
)
LOCATIONS = (("00123", True), ("2", False), ("123", True))
GEOGRAPHY = (("00123",), ("00123",), ("123",))


def render(relative: str) -> str:
    environment = pytest.importorskip("jinja2").Environment(
        undefined=pytest.importorskip("jinja2").StrictUndefined
    )

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        ref=lambda name: name,
        config=config,
    )


def contract() -> dict:
    return pytest.importorskip("yaml").safe_load(
        (PROJECT / "models/core/dim_seller.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str, name: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = dict(definition[name]["arguments"]) if isinstance(definition, dict) else {}
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    if "to" in arguments:
        arguments["to"] = environment.from_string("{{ " + arguments["to"] + " }}").render(
            ref=lambda model: model
        )
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql" / (name + ".sql")
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(module, "default__test_" + name)(
        model="dim_seller", column_name=column, **arguments
    )


def sqlite_except_all(statement: str) -> str:
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
            + f" on {matches} and l.occurrence=r.occurrence where r.occurrence is null"
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
    sellers: tuple[tuple[object, ...], ...] = SELLERS,
    locations: tuple[tuple[object, ...], ...] = LOCATIONS,
    geography: tuple[tuple[object, ...], ...] = GEOGRAPHY,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_sellers", COLUMNS[:-1], sellers),
        ("dim_location", ("zip_code_prefix", "has_geolocation"), locations),
        ("stg_geolocation", ("geolocation_zip_code_prefix",), geography),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/dim_seller.sql") + ")")
    fields = ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
    ctes.append(f"dim_seller as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(*generic)
        if generic
        else "select * from dim_seller"
    )
    statement = sqlite_except_all(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    ).replace(" !~ ", " not regexp ")
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
        connection.create_function(
            "regexp",
            2,
            lambda pattern, value: (
                None if value is None else int(re.fullmatch(pattern, value) is not None)
            ),
        )
        connection.execute("pragma query_only=on")
        result = connection.execute(statement, values)
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()


def test_seller_preserves_literal_fields_lineage_and_grain_with_coverage() -> None:
    assert run_sql() == [
        (*row, flag) for row, flag in zip(SELLERS, (True, True, False), strict=True)
    ]
    assert run_sql("seller_dimension_source_reconciliation") == []
    assert run_sql("seller_dimension_domains") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert [item["data_type"] for item in contract()["columns"]] == [
        "uuid",
        "bigint",
        *["text"] * 4,
        "boolean",
    ]
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("seller_id", "unique")) == []
    assert run_sql(generic=("seller_zip_code_prefix", "relationships")) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_required_tests_reject_each_null_output(column: str) -> None:
    assert run_sql(generic=(column, "not_null"), changes={column: "null"})


def test_missing_required_location_is_retained_with_null_coverage_and_blocked() -> None:
    locations = (LOCATIONS[0], LOCATIONS[2])
    assert run_sql(locations=locations)[-1] == (*SELLERS[-1], None)
    assert run_sql(generic=("has_geolocation", "not_null"), locations=locations)
    assert run_sql(generic=("seller_zip_code_prefix", "relationships"), locations=locations) == [
        ("2",)
    ]
    assert run_sql("seller_dimension_source_reconciliation", locations=locations) == [(1, 1)]


def test_duplicate_zip_reference_fanout_is_detected_without_deduplicating_sellers() -> None:
    locations = (*LOCATIONS, LOCATIONS[0])
    assert len(run_sql(locations=locations)) == 5
    assert run_sql(generic=("seller_id", "unique"), locations=locations)
    assert run_sql("seller_dimension_source_reconciliation", locations=locations) == [(0, 2)]


def test_incorrect_dimension_coverage_fails_independent_geography_reconciliation() -> None:
    locations = (("00123", False), ("2", True), ("123", True))
    assert run_sql("seller_dimension_source_reconciliation", locations=locations) == [(3, 3)]


@pytest.mark.parametrize(
    "changes",
    [
        {"_load_id": "'22222222-2222-4222-8222-222222222222'"},
        {"_source_row": "_source_row + 10"},
        {"seller_id": "'dddddddddddddddddddddddddddddddd'"},
        {"seller_zip_code_prefix": "'99999'"},
        {"seller_city": "'altered'"},
        {"seller_state": "'SP'"},
        {"has_geolocation": "not has_geolocation"},
    ],
)
def test_all_field_substitutions_fail_bidirectional_reconciliation(changes: dict[str, str]) -> None:
    assert run_sql("seller_dimension_source_reconciliation", changes=changes)


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "seller_id <> 'cccccccccccccccccccccccccccccccc'"}, (1, 0)),
        ({"suffix": " union all select * from projected"}, (0, 3)),
    ],
)
def test_lost_uncovered_or_duplicated_sellers_fail_reconciliation(
    corruption: dict, expected: tuple[int, int]
) -> None:
    assert run_sql("seller_dimension_source_reconciliation", **corruption) == [expected]


@pytest.mark.parametrize(
    "column,value",
    [
        ("seller_id", "'ABC'"),
        ("seller_zip_code_prefix", "'１２３'"),
        ("seller_zip_code_prefix", "'123456'"),
        ("seller_zip_code_prefix", "' 1 '"),
        ("_source_row", "0"),
        ("seller_state", "'sp'"),
        ("seller_state", "'XX'"),
    ],
)
def test_domain_guard_rejects_invalid_preserved_values(column: str, value: str) -> None:
    assert run_sql("seller_dimension_domains", changes={column: value})


def test_empty_seller_source_produces_empty_valid_dimension() -> None:
    assert run_sql(sellers=()) == []
    assert run_sql("seller_dimension_domains", sellers=()) == []
    assert run_sql("seller_dimension_source_reconciliation", sellers=()) == []
