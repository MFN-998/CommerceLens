"""Execute the location dimension and actual dbt tests on bound synthetic inputs.

Query-only, in-memory SQLite checks row semantics, literal spellings and deliberate
dimension corruption. Row-numbered subtraction preserves EXCEPT ALL multiplicity.
Native PostgreSQL remains authoritative for physical types and database collation.
No source data, persistent fixture files or project resources are modified.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "zip_code_prefix",
    "geolocation_observation_count",
    "geolocation_city_variant_count",
    "geolocation_state_variant_count",
    "outside_broad_brazil_observation_count",
    "has_geolocation",
    "is_geolocation_city_ambiguous",
    "is_geolocation_state_ambiguous",
)
CUSTOMERS = (("01001",), ("01001",), ("1",), ("99999",))
SELLERS = (("01001",), ("2",), ("99999",))
GEOLOCATION = (
    ("01001", "São Paulo", "SP", False),
    ("01001", "São Paulo", "SP", False),
    ("01001", "são paulo", "SP", True),
    ("01001", "São Paulo ", "RJ", True),
    ("00001", "Manaus", "AM", False),
    ("1", "Short prefix", "SP", False),
)
SINGULARS = ("domains", "source_reconciliation", "join_conservation")


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")

    def ref(name: str) -> str:
        assert name in {
            "stg_customers",
            "stg_sellers",
            "stg_geolocation",
            "dim_location",
        }
        return name

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string((PROJECT / relative_path).read_text("utf-8"))
        .render(ref=ref, config=config)
    )


def model_contract() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((PROJECT / "models/core/dim_location.yml").read_text("utf-8"))["models"][
        0
    ]


def render_generic(column: str, name: str) -> str:
    """Render installed dbt macros selected by the actual dimension YAML."""
    jinja2 = pytest.importorskip("jinja2")
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    tests = next(record for record in model_contract()["columns"] if record["name"] == column)[
        "data_tests"
    ]
    assert name in tests
    path = Path(spec.origin).parent / "macros/generic_test_sql" / f"{name}.sql"
    macros = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string(path.read_text("utf-8"))
        .make_module({"should_store_failures": lambda: False})
    )
    return getattr(macros, f"default__test_{name}")(model="dim_location", column_name=column)


def sqlite_except_all(statement: str) -> str:
    """NULL-safe multiset subtraction, including repeated dimension rows."""

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        fields = ", ".join(COLUMNS)
        matches = " and ".join(f"lhs.{column} is rhs.{column}" for column in COLUMNS)
        return (
            "select "
            + ", ".join("lhs." + column for column in COLUMNS)
            + f" from (select *, row_number() over (partition by {fields}) as occurrence"
            + f" from {left}) lhs left join (select *, row_number() over (partition by"
            + f" {fields}) as occurrence from {right}) rhs on {matches}"
            + " and lhs.occurrence=rhs.occurrence where rhs.occurrence is null"
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
    customers: tuple[tuple[object, ...], ...] = CUSTOMERS,
    sellers: tuple[tuple[object, ...], ...] = SELLERS,
    geolocation: tuple[tuple[object, ...], ...] = GEOLOCATION,
    changes: dict[str, str] | None = None,
    dimension_filter: str = "true",
    dimension_suffix: str = "",
) -> list[tuple[object, ...]]:
    """Execute actual projection/test SQL; corruption affects only its output CTE."""
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    inputs = (
        ("stg_customers", ("customer_zip_code_prefix",), customers),
        ("stg_sellers", ("seller_zip_code_prefix",), sellers),
        (
            "stg_geolocation",
            (
                "geolocation_zip_code_prefix",
                "geolocation_city",
                "geolocation_state",
                "is_outside_broad_brazil_bounds",
            ),
            geolocation,
        ),
    )
    ctes, parameters = [], []
    for name, columns, rows in inputs:
        values = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({values})")
        parameters.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render_sql("models/core/dim_location.sql") + ")")
    fields = ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
    ctes.append(
        f"dim_location as (select {fields} from projected where {dimension_filter}"
        + dimension_suffix
        + ")"
    )
    query = (
        render_sql(f"tests/dim_location_{singular}.sql")
        if singular
        else render_generic(*generic)
        if generic
        else "select * from dim_location"
    )
    statement = "with " + ", ".join(ctes) + " select * from (" + query + ") as result"
    statement = sqlite_except_all(
        statement.replace(" !~ ", " not regexp ").replace(" is distinct from ", " is not ")
    )
    connection = sqlite3.connect(":memory:")
    try:
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
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()
    finally:
        connection.close()


def test_minimal_contract_is_private_core_view_with_eight_required_columns() -> None:
    contract = model_contract()
    assert contract["name"] == "dim_location"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(column["name"] for column in contract["columns"]) == COLUMNS
    assert [column["data_type"] for column in contract["columns"]] == (
        ["text"] + ["bigint"] * 4 + ["boolean"] * 3
    )
    assert sum(len(column["data_tests"]) for column in contract["columns"]) == 9


def test_literal_union_preserves_duplicate_observations_and_uncovered_addresses() -> None:
    assert sorted(run_sql()) == [
        ("00001", 1, 1, 1, 0, 1, 0, 0),
        ("01001", 4, 3, 2, 2, 1, 1, 1),
        ("1", 1, 1, 1, 0, 1, 0, 0),
        ("2", 0, 0, 0, 0, 0, 0, 0),
        ("99999", 0, 0, 0, 0, 0, 0, 0),
    ]
    assert sum(row[1] for row in run_sql()) == len(GEOLOCATION)
    assert sum(row[4] for row in run_sql()) == 2
    for singular in SINGULARS:
        assert run_sql(singular) == []
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("zip_code_prefix", "unique")) == []


@pytest.mark.parametrize(
    "city", ["são paulo", "Sao Paulo", "São Paulo ", " São Paulo", "São Paulo"]
)
def test_literal_city_variants_are_not_trimmed_casefolded_or_accent_normalized(
    city: str,
) -> None:
    rows = (("01001", "São Paulo", "SP", False), ("01001", city, "SP", False))
    expected_variants = 1 if city == "São Paulo" else 2
    assert run_sql(customers=(), sellers=(), geolocation=rows) == [
        ("01001", 2, expected_variants, 1, 0, 1, int(expected_variants > 1), 0)
    ]
    assert run_sql("source_reconciliation", customers=(), sellers=(), geolocation=rows) == []


def test_empty_sources_produce_empty_dimension_without_false_failures() -> None:
    assert run_sql(customers=(), sellers=(), geolocation=()) == []
    for singular in SINGULARS:
        assert run_sql(singular, customers=(), sellers=(), geolocation=()) == []


def test_all_sources_with_null_zip_retain_visible_blocking_dimension_row() -> None:
    inputs = {
        "customers": ((None,),),
        "sellers": ((None,),),
        "geolocation": ((None, "City", "SP", False),),
    }
    assert run_sql(**inputs) == [(None, 0, 0, 0, 0, 0, 0, 0)]
    assert run_sql("domains", **inputs) == [(3, 0, 1)]
    assert run_sql(generic=("zip_code_prefix", "not_null"), **inputs) == [(None,)]


@pytest.mark.parametrize("source", ["customers", "sellers", "geolocation"])
@pytest.mark.parametrize("prefix", [None, "", "ABC", "１２３", "123456", " 1 "])
def test_invalid_upstream_zip_is_retained_and_blocked(source: str, prefix: object) -> None:
    inputs = {"customers": (), "sellers": (), "geolocation": ()}
    inputs[source] = ((prefix, "City", "SP", False),) if source == "geolocation" else ((prefix,),)
    assert run_sql(**inputs)[0][0] == prefix
    assert run_sql("domains", **inputs)
    if prefix is None:
        assert run_sql(generic=("zip_code_prefix", "not_null"), **inputs)


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_not_null_tests_block_null_dimension_values(column: str) -> None:
    assert run_sql(generic=(column, "not_null"), changes={column: "null"})


@pytest.mark.parametrize("missing_index", [1, 2, 3])
def test_null_geography_consumed_input_is_blocked_even_when_valid_variant_remains(
    missing_index: int,
) -> None:
    valid = ("01001", "City", "SP", False)
    missing = tuple(None if index == missing_index else value for index, value in enumerate(valid))
    inputs = {"customers": (), "sellers": (), "geolocation": (valid, missing)}
    assert run_sql(**inputs) == [("01001", 2, 1, 1, 0, 1, 0, 0)]
    assert run_sql("source_reconciliation", **inputs) == []
    assert run_sql("domains", **inputs) == [(0, 1, 0)]


@pytest.mark.parametrize(
    "changes",
    [{column: "-1"} for column in COLUMNS[1:5]]
    + [{column: "geolocation_observation_count + 1"} for column in COLUMNS[2:5]]
    + [
        {"geolocation_city_variant_count": "0"},
        {"geolocation_state_variant_count": "0"},
    ]
    + [{column: "not " + column} for column in COLUMNS[5:]]
    + [{column: "null"} for column in COLUMNS[5:]],
)
def test_count_bounds_and_derived_flags_block_corruption(
    changes: dict[str, str],
) -> None:
    failures = run_sql("domains", changes=changes)
    assert len(failures) == 1 and failures[0][2] > 0


@pytest.mark.parametrize(
    "corruption",
    [
        {"dimension_filter": "zip_code_prefix <> '01001'"},
        {"dimension_filter": "zip_code_prefix <> '99999'"},
        {"dimension_suffix": " union all select '99998', 0, 0, 0, 0, false, false, false"},
        {"dimension_suffix": " union all select * from projected where zip_code_prefix = '01001'"},
        {
            "changes": {
                "zip_code_prefix": (
                    "case when zip_code_prefix='01001' then '01002' else zip_code_prefix end"
                )
            }
        },
        {"changes": {"outside_broad_brazil_observation_count": "0"}},
        {
            "changes": {
                "geolocation_observation_count": (
                    "case when zip_code_prefix='01001' then 3 "
                    "when zip_code_prefix='00001' then 2 "
                    "else geolocation_observation_count end"
                )
            }
        },
    ],
)
def test_bidirectional_reconciliation_blocks_missing_extra_duplicate_and_changed_rows(
    corruption: dict,
) -> None:
    failures = run_sql("source_reconciliation", **corruption)
    assert len(failures) == 1 and sum(failures[0]) > 0


def test_actual_unique_test_detects_repeated_dimension_key() -> None:
    assert run_sql(
        generic=("zip_code_prefix", "unique"),
        dimension_suffix=" union all select * from projected where zip_code_prefix='01001'",
    ) == [("01001", 2)]


@pytest.mark.parametrize(
    "corruption",
    [
        {"dimension_filter": "zip_code_prefix <> '99999'"},
        {"dimension_suffix": " union all select * from projected where zip_code_prefix='01001'"},
        {"changes": {"has_geolocation": "true"}},
    ],
)
def test_join_conservation_blocks_address_loss_fanout_and_false_coverage(
    corruption: dict,
) -> None:
    failures = run_sql("join_conservation", **corruption)
    assert len(failures) == 1 and failures[0][0] > 0
