"""Execute geolocation projection, singular and actual dbt generic SQL offline.

Only bound synthetic VALUES enter query-only in-memory SQLite. The REGEXP and
double-input shims exercise guarded projection and small coordinate cases; the
row-numbered subtraction adapts EXCEPT ALL without losing duplicate multiplicity.
SQLite cannot prove PostgreSQL floating-point representability, physical types,
collation, or planner behavior. Native PostgreSQL acceptance remains authoritative.
No dataset, persistent database, fixture files, or project resources are modified.
"""

from __future__ import annotations

import importlib.util
import math
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_city",
    "geolocation_state",
)
COORDINATES = COLUMNS[3:5]
FLAG = "is_outside_broad_brazil_bounds"
EXPECTED_COLUMNS = (*COLUMNS, FLAG)
LOAD = "11111111-1111-4111-8111-111111111111"
STATES = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)


def geolocation(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(COLUMNS, (LOAD, 1, "01001", "-23.55", "-46.63", "São Paulo", "SP"), strict=True)
    )
    assert set(changes) <= set(values)
    values.update(changes)
    return tuple(values[column] for column in COLUMNS)


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = (PROJECT / "macros/source_numeric.sql").read_text("utf-8")

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "geolocation")
        return "synthetic_geolocation"

    def ref(name: str) -> str:
        assert name == "stg_geolocation"
        return "synthetic_staged"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        environment.from_string(macros + "\n" + (PROJECT / relative_path).read_text("utf-8"))
        .render(source=source, ref=ref, config=config)
        .strip()
    )


def model_contract() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((PROJECT / "models/staging/stg_geolocation.yml").read_text("utf-8"))[
        "models"
    ][0]


def render_generic(column: str, name: str) -> str:
    """Use installed dbt generic SQL and actual geolocation YAML arguments."""
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
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = environment.from_string(path.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(macros, f"default__test_{name}")(
        model="synthetic_staged", column_name=column, **arguments
    )


def sqlite_input_valid(value: str | None, type_name: str) -> int | None:
    """Limited double adapter; native PostgreSQL is the representability oracle."""
    assert type_name == "double precision"
    if value is None:
        return None
    try:
        number = Decimal(value)
        parsed = float(value)
        return int(number.is_finite() and math.isfinite(parsed) and (parsed != 0 or number == 0))
    except (InvalidOperation, ValueError, OverflowError):
        return 0


def sqlite_except_all(statement: str) -> str:
    """NULL-safe duplicate-preserving multiset subtraction for SQLite."""

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        partition = ", ".join(EXPECTED_COLUMNS)
        matches = " and ".join(f"lhs.{column} is rhs.{column}" for column in EXPECTED_COLUMNS)
        return (
            "select "
            + ", ".join("lhs." + column for column in EXPECTED_COLUMNS)
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
) -> list[tuple[object, ...]]:
    """Execute actual model/test SQL with bound inputs and staged corruption."""
    assert not (singular and generic)
    assert rows
    changes = changes or {}
    assert set(changes) <= set(EXPECTED_COLUMNS)
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    query = (
        render_sql(singular)
        if singular
        else render_generic(*generic)
        if generic
        else "select * from synthetic_staged"
    )
    fields = ", ".join(changes.get(column, column) + " as " + column for column in EXPECTED_COLUMNS)
    statement = (
        "with synthetic_geolocation ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), projected as ("
        + render_sql("models/staging/stg_geolocation.sql")
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
    statement = sqlite_except_all(statement)
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
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
        result = connection.execute(statement, tuple(value for row in rows for value in row))
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == EXPECTED_COLUMNS
        return result.fetchall()
    finally:
        connection.close()


def test_literal_zip_city_state_lineage_and_exact_duplicate_observations_are_retained() -> None:
    rows = [
        geolocation(geolocation_city="  São João d'Água / café  "),
        geolocation(_source_row=2, geolocation_city="  São João d'Água / café  "),
    ]
    staged = run_sql(rows)
    assert len(staged) == 2
    for source, actual in zip(rows, staged, strict=True):
        assert actual[:3] == source[:3]
        assert actual[3:5] == (float(source[3]), float(source[4]))
        assert actual[5:7] == source[5:7]
        assert actual[7] == 0
    assert run_sql(rows, "tests/stg_geolocation_lineage_unique.sql") == []
    assert run_sql(rows, "tests/stg_geolocation_source_domains.sql") == []
    assert run_sql(rows, "tests/stg_geolocation_source_reconciliation.sql") == []


def test_same_zip_with_distinct_observations_is_not_collapsed_to_a_canonical_coordinate() -> None:
    rows = [geolocation(), geolocation(_source_row=2, geolocation_lat="-23.56")]
    assert [row[2:5] for row in run_sql(rows)] == [
        ("01001", -23.55, -46.63),
        ("01001", -23.56, -46.63),
    ]
    assert run_sql(rows, "tests/stg_geolocation_lineage_unique.sql") == []
    assert run_sql(rows, "tests/stg_geolocation_source_reconciliation.sql") == []


def test_whitespace_city_is_preserved_without_trimming_or_case_normalization() -> None:
    source = geolocation(geolocation_city=" \t\n")
    assert run_sql([source])[0][5] == " \t\n"
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == []


@pytest.mark.parametrize("column", COLUMNS[2:])
@pytest.mark.parametrize("missing", ["", None])
def test_missing_mandatory_source_field_retains_row_and_blocks(
    column: str, missing: object
) -> None:
    source = geolocation(**{column: missing})
    actual = run_sql([source])[0]
    assert actual[COLUMNS.index(column)] is None
    assert actual[-1] == 0
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=(column, "not_null")) == [(None,)]
    assert run_sql([source], "tests/stg_geolocation_source_reconciliation.sql") == []


@pytest.mark.parametrize("column", EXPECTED_COLUMNS)
def test_actual_dbt_not_null_blocks_missing_lineage_attribute_or_flag(column: str) -> None:
    assert run_sql([geolocation()], generic=(column, "not_null"), changes={column: "null"}) == [
        (None,)
    ]


@pytest.mark.parametrize("zip_prefix", ["1", "1001", "00000"])
def test_short_ascii_zip_and_leading_zero_zip_are_retained_without_padding(zip_prefix: str) -> None:
    source = geolocation(geolocation_zip_code_prefix=zip_prefix)
    assert run_sql([source])[0][2] == zip_prefix
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == []


@pytest.mark.parametrize("zip_prefix", ["010010", " 01001", "01001 ", "０１００１", "01x01"])
def test_invalid_zip_literal_is_not_padded_trimmed_or_rewritten(zip_prefix: str) -> None:
    source = geolocation(geolocation_zip_code_prefix=zip_prefix)
    assert run_sql([source])[0][2] == zip_prefix
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("state", ["sp", " SP", "SP ", "ZZ"])
def test_invalid_state_is_literal_and_blocks_domain_and_actual_accepted_values(state: str) -> None:
    source = geolocation(geolocation_state=state)
    assert run_sql([source])[0][6] == state
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=("geolocation_state", "accepted_values")) == [(state, 1)]


@pytest.mark.parametrize("text,expected", [(" \t-2.355e1\n", -23.55), ("+0.0", 0.0)])
def test_coordinate_uses_existing_guarded_decimal_double_projection(
    text: str, expected: float
) -> None:
    source = geolocation(geolocation_lat=text)
    assert run_sql([source])[0][3] == expected
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == []


@pytest.mark.parametrize("column", COORDINATES)
@pytest.mark.parametrize("text", ["bad", "NaN", "Infinity", "1_000", "1e309", "1e-400"])
def test_rejected_coordinate_is_null_retains_observation_and_blocks(column: str, text: str) -> None:
    source = geolocation(**{column: text})
    actual = run_sql([source])[0]
    assert actual[COLUMNS.index(column)] is None
    assert actual[-1] == 0
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]
    assert run_sql([source], "tests/stg_geolocation_source_reconciliation.sql") == []


@pytest.mark.parametrize(
    "latitude,longitude,flag",
    [
        ("-34", "-74", 0),
        ("6", "-28", 0),
        ("-34.0001", "-46", 1),
        ("6.0001", "-46", 1),
        ("-23", "-74.0001", 1),
        ("-23", "-27.9999", 1),
        ("0", "0", 1),
    ],
)
def test_broad_brazil_boundary_warning_is_inclusive_and_never_filters_observations(
    latitude: str, longitude: str, flag: int
) -> None:
    source = geolocation(geolocation_lat=latitude, geolocation_lng=longitude)
    assert run_sql([source])[0][3:] == (float(latitude), float(longitude), "São Paulo", "SP", flag)
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == []
    assert run_sql([source], "tests/stg_geolocation_source_reconciliation.sql") == []


@pytest.mark.parametrize(
    "column,coordinate",
    [
        ("geolocation_lat", "-90"),
        ("geolocation_lat", "90"),
        ("geolocation_lng", "-180"),
        ("geolocation_lng", "180"),
    ],
)
def test_global_coordinate_boundary_remains_valid_even_outside_brazil(
    column: str, coordinate: str
) -> None:
    source = geolocation(**{column: coordinate})
    assert run_sql([source])[0][COLUMNS.index(column)] == float(coordinate)
    assert run_sql([source])[0][-1] == 1
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == []


@pytest.mark.parametrize(
    "column,coordinate",
    [
        ("geolocation_lat", "-90.01"),
        ("geolocation_lat", "90.01"),
        ("geolocation_lng", "-180.01"),
        ("geolocation_lng", "180.01"),
    ],
)
def test_global_coordinate_violation_remains_typed_and_blocks(column: str, coordinate: str) -> None:
    source = geolocation(**{column: coordinate})
    assert run_sql([source])[0][COLUMNS.index(column)] == float(coordinate)
    assert run_sql([source])[0][-1] == 1
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", COORDINATES)
def test_missing_coordinate_does_not_infer_brazil_warning_from_the_other_coordinate(
    column: str,
) -> None:
    changes = {"geolocation_lat": "90", "geolocation_lng": "180", column: ""}
    source = geolocation(**changes)
    assert run_sql([source])[0][-1] == 0
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]


def test_duplicate_lineage_is_retained_but_blocks_and_ordinal_can_repeat_in_another_load() -> None:
    source = geolocation()
    assert len(run_sql([source, source])) == 2
    assert run_sql([source, source], "tests/stg_geolocation_lineage_unique.sql") == [(1,)]
    rows = [source, geolocation(_load_id="22222222-2222-4222-8222-222222222222")]
    assert run_sql(rows, "tests/stg_geolocation_lineage_unique.sql") == []


@pytest.mark.parametrize("ordinal", [None, 0, -1])
def test_missing_or_nonpositive_source_ordinal_blocks(ordinal: object) -> None:
    source = geolocation(_source_row=ordinal)
    assert run_sql([source])[0][1] == ordinal
    assert run_sql([source], "tests/stg_geolocation_source_domains.sql") == [(1,)]


@pytest.mark.parametrize(
    "column,expression",
    [
        ("_load_id", "'22222222-2222-4222-8222-222222222222'"),
        ("_source_row", "_source_row+1"),
        ("geolocation_zip_code_prefix", "'01002'"),
        ("geolocation_lat", "geolocation_lat+0.01"),
        ("geolocation_lng", "geolocation_lng+0.01"),
        ("geolocation_city", "'changed city'"),
        ("geolocation_state", "'RJ'"),
        (FLAG, "true"),
    ],
)
def test_multiset_reconciliation_detects_each_attribute_lineage_or_warning_substitution(
    column: str, expression: str
) -> None:
    assert run_sql(
        [geolocation()],
        "tests/stg_geolocation_source_reconciliation.sql",
        changes={column: expression},
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_distinguishes_missing_literal_city_from_empty_text() -> None:
    source = geolocation(geolocation_city="")
    assert run_sql([source], "tests/stg_geolocation_source_reconciliation.sql") == []
    assert run_sql(
        [source],
        "tests/stg_geolocation_source_reconciliation.sql",
        changes={"geolocation_city": "''"},
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_dropped_extra_and_count_preserving_duplicate_changes() -> (
    None
):
    rows = [geolocation(), geolocation(_source_row=2)]
    test = "tests/stg_geolocation_source_reconciliation.sql"
    assert run_sql(rows, test, staged_filter="_source_row<>1") == [("missing_from_staging", 1)]
    assert run_sql(
        rows, test, staged_suffix=" union all select * from projected where _source_row=1"
    ) == [("unexpected_in_staging", 1)]
    assert run_sql(
        rows,
        test,
        staged_filter="_source_row=1",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_contract_uses_observation_lineage_without_unique_zip_or_coordinate_and_twelve_tests() -> (
    None
):
    contract = model_contract()
    assert contract["config"] == {"materialized": "view", "schema": "staging"}
    columns = contract["columns"]
    assert tuple(record["name"] for record in columns) == EXPECTED_COLUMNS
    assert tuple(record["data_type"] for record in columns) == (
        "uuid",
        "bigint",
        "text",
        "double precision",
        "double precision",
        "text",
        "text",
        "boolean",
    )
    assert all("not_null" in record["data_tests"] for record in columns)
    assert all("unique" not in record["data_tests"] for record in columns)
    assert sum(len(record.get("data_tests", [])) for record in columns) + 3 == 12
    state = next(record for record in columns if record["name"] == "geolocation_state")
    assert set(state["data_tests"][1]["accepted_values"]["arguments"]["values"]) == set(STATES)
