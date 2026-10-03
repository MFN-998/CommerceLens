"""Native geolocation checks using bounded synthetic, read-only VALUES inputs.

Render the real staging model/macros, singular tests and YAML-configured generic
tests. Independent literals verify finite coordinates, literal address text and
inclusive broad-Brazil/global bounds. No raw records, fixture tables, temporary
relations, or warehouse writes are used. ZIPs and complete observations repeat;
only load/ordinal lineage is unique. Reconciliation checks full row multisets.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_GEOLOCATION_INTEGRATION") != "1",
    reason="Native read-only geolocation SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
OTHER_LOAD = UUID("22222222-2222-4222-8222-222222222222")
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["geolocation"].columns)
COORDINATE_COLUMNS = ("geolocation_lat", "geolocation_lng")
TEXT_COLUMNS = ("geolocation_zip_code_prefix", "geolocation_city", "geolocation_state")
MANDATORY_SOURCE = tuple(TABLES["geolocation"].columns)
FLAG = "is_outside_broad_brazil_bounds"
EXPECTED_COLUMNS = (*SOURCE_COLUMNS, FLAG)

# No expected coordinate invokes a production macro or the Phase 2 parser.
BOUND_CASES = (
    ("south-west-inclusive", "-34", "-74", -34.0, -74.0, False, 0),
    ("north-east-inclusive", "6", "-28", 6.0, -28.0, False, 0),
    ("just-south", "-34.0001", "-46", -34.0001, -46.0, True, 0),
    ("just-north", "6.0001", "-46", 6.0001, -46.0, True, 0),
    ("just-west", "-23", "-74.0001", -23.0, -74.0001, True, 0),
    ("just-east", "-23", "-27.9999", -23.0, -27.9999, True, 0),
    ("global-lower-inclusive", "-90", "-180", -90.0, -180.0, True, 0),
    ("global-upper-inclusive", "90", "180", 90.0, 180.0, True, 0),
    ("below-global-latitude", "-90.0001", "-46", -90.0001, -46.0, True, 1),
    ("above-global-latitude", "90.0001", "-46", 90.0001, -46.0, True, 1),
    ("below-global-longitude", "-23", "-180.0001", -23.0, -180.0001, True, 1),
    ("above-global-longitude", "-23", "180.0001", -23.0, 180.0001, True, 1),
)
INVALID_COORDINATES = (
    ("malformed", "not-a-number"),
    ("whitespace", " \t\n"),
    ("nan-extension", "NaN"),
    ("positive-infinity-extension", "Infinity"),
    ("negative-infinity-extension", "-Infinity"),
    ("overflow", "1e309"),
    ("underflow-must-not-invent-zero", "1e-400"),
    ("unrepresentable-exponent", "1e99999999999999999999999"),
)


def _source_row(changes: dict[str, object] | None = None) -> tuple[object, ...]:
    fields: dict[str, object] = {
        "_load_id": LOAD,
        "_source_row": 1,
        "geolocation_zip_code_prefix": "00123",
        "geolocation_lat": "-23.550520123456789",
        "geolocation_lng": "-46.6333087654321",
        "geolocation_city": "São Paulo",
        "geolocation_state": "SP",
    }
    fields.update(changes or {})
    return tuple(fields[column] for column in SOURCE_COLUMNS)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_sql(relative_path: str) -> str:
    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "geolocation")
        return "synthetic_geolocation"

    def ref(model: str) -> str:
        assert model == "stg_geolocation"
        return "synthetic_projection"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = (PROJECT / "macros/source_numeric.sql").read_text("utf-8")
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        _environment()
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_test_sql(column_name: str, name: str) -> str:
    # Read the actual model YAML, including the accepted literal state list.
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/staging/stg_geolocation.yml").read_text("utf-8"))[
        "models"
    ][0]
    tests = next(column for column in contract["columns"] if column["name"] == column_name)[
        "data_tests"
    ]
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = definition[name]["arguments"].copy() if isinstance(definition, dict) else {}
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name, **arguments
    ).strip()


def _synthetic_cte(
    rows: tuple[tuple[object, ...], ...],
    *,
    materialized: bool = True,
    overrides: dict[str, object] | None = None,
    stage_mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert 1 <= len(rows) <= 4
    assert all(len(row) == len(SOURCE_COLUMNS) for row in rows)
    assert stage_mode in {"same", "distinct", "duplicate", "empty"}
    changes = overrides or {}
    assert set(changes) <= {*TEXT_COLUMNS, *COORDINATE_COLUMNS, FLAG}
    assert not changes or stage_mode == "same"
    # MATERIALIZED mimics raw text columns; inline VALUES probes planner folding
    # of unreachable casts. Explicit input types preserve synthetic NULL shape.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in SOURCE_COLUMNS[2:]))
    value_row = "(" + ", ".join(placeholders) + ")"
    materialization = "materialized " if materialized else ""
    ctes = [
        "synthetic_geolocation ("
        + ", ".join(SOURCE_COLUMNS)
        + ") as "
        + materialization
        + "(values "
        + ", ".join(value_row for _ in rows)
        + ")",
        "synthetic_actual_projection as ("
        + _render_sql("models/staging/stg_geolocation.sql")
        + ")",
    ]
    parameters = [value for row in rows for value in row]
    fields = []
    for column in EXPECTED_COLUMNS:
        if column in changes:
            if column == FLAG:
                type_name = "boolean"
            elif column in COORDINATE_COLUMNS:
                type_name = "double precision"
            else:
                type_name = "text"
            fields.append("%s::" + type_name + " as " + column)
            parameters.append(changes[column])
        else:
            fields.append(column)
    selection = (
        "select "
        + ("distinct " if stage_mode == "distinct" else "")
        + ", ".join(fields)
        + " from synthetic_actual_projection"
    )
    if stage_mode == "duplicate":
        selection += " union all select * from synthetic_actual_projection"
    elif stage_mode == "empty":
        selection += " where false"
    ctes.append("synthetic_projection as (" + selection + ")")
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    # Hide setup exception details, which can contain private connection input.
    # SQL assertions below use only bounded, deliberately synthetic literals.
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
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
            "Geolocation native check setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    """A failing case rolls back its savepoint without poisoning later cases."""
    with transformer_connection.transaction():
        yield


def _projection(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    *,
    materialized: bool = True,
) -> list[dict[str, object]]:
    cte, parameters = _synthetic_cte(rows, materialized=materialized)
    # Read actual binary64 values: the dev session's extra_float_digits=0 rounds
    # text output to 15 significant digits. Keep exact independent assertions;
    # do not mistake transport formatting for a model conversion or loosen them.
    result = connection.execute(
        cte + "select * from synthetic_projection order by _load_id, _source_row",
        parameters,
        binary=True,
    )
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == EXPECTED_COLUMNS
    records = result.fetchall()
    assert len(records) == len(rows)
    return [dict(zip(names, record, strict=True)) for record in records]


def _single_projection(
    connection: psycopg.Connection, row: tuple[object, ...], *, materialized: bool = True
) -> dict[str, object]:
    return _projection(connection, (row,), materialized=materialized)[0]


def _singular_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    filename: str,
    expected_column: str,
) -> int:
    cte, parameters = _synthetic_cte(rows)
    result = connection.execute(
        cte + "select * from (" + _render_sql("tests/" + filename) + ") as singular_result",
        parameters,
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == (expected_column,)
    records = result.fetchall()
    if not records:
        return 0
    assert len(records) == 1
    return records[0][0]


def _domain_failures(connection: psycopg.Connection, row: tuple[object, ...]) -> int:
    return _singular_failures(
        connection, (row,), "stg_geolocation_source_domains.sql", "invalid_source_value_rows"
    )


def _generic_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    column: str,
    name: str,
) -> int:
    cte, parameters = _synthetic_cte(rows)
    result = connection.execute(
        cte + "select count(*) from (" + _generic_test_sql(column, name) + ") as generic_result",
        parameters,
    ).fetchone()
    assert result is not None
    return result[0]


def _reconciliation(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    *,
    overrides: dict[str, object] | None = None,
    stage_mode: str = "same",
) -> list[tuple[str, int]]:
    cte, parameters = _synthetic_cte(rows, overrides=overrides, stage_mode=stage_mode)
    result = connection.execute(
        cte
        + "select * from ("
        + _render_sql("tests/stg_geolocation_source_reconciliation.sql")
        + ") as reconciliation_result order by mismatch",
        parameters,
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == ("mismatch", "row_count")
    return result.fetchall()


def _assert_flag(projected: dict[str, object], expected: bool = False) -> None:
    assert type(projected[FLAG]) is bool
    assert projected[FLAG] is expected


def test_exact_decimal_coordinates_have_float_types_without_rounding_or_repair(
    transformer_connection: psycopg.Connection,
) -> None:
    projected = _single_projection(transformer_connection, _source_row())
    assert projected["geolocation_lat"] == -23.550520123456789
    assert projected["geolocation_lng"] == -46.6333087654321
    assert all(type(projected[column]) is float for column in COORDINATE_COLUMNS)
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, _source_row()) == 0


def test_finite_decimal_exponent_and_input_whitespace_are_parseable_coordinates(
    transformer_connection: psycopg.Connection,
) -> None:
    row = _source_row({"geolocation_lat": " \t+1.25e0\n", "geolocation_lng": " -4.75e1 "})
    projected = _single_projection(transformer_connection, row)
    assert projected["geolocation_lat"] == 1.25
    assert projected["geolocation_lng"] == -47.5
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 0


def test_zero_coordinates_remain_valid_values_with_an_exploratory_outside_flag(
    transformer_connection: psycopg.Connection,
) -> None:
    row = _source_row({"geolocation_lat": "0", "geolocation_lng": "0.0"})
    projected = _single_projection(transformer_connection, row)
    assert projected["geolocation_lat"] == 0.0
    assert projected["geolocation_lng"] == 0.0
    assert all(type(projected[column]) is float for column in COORDINATE_COLUMNS)
    _assert_flag(projected, True)
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize(
    "latitude,longitude,expected_latitude,expected_longitude,outside,failures",
    [case[1:] for case in BOUND_CASES],
    ids=[case[0] for case in BOUND_CASES],
)
def test_inclusive_broad_box_warns_while_only_global_domain_violation_blocks(
    transformer_connection: psycopg.Connection,
    latitude: str,
    longitude: str,
    expected_latitude: float,
    expected_longitude: float,
    outside: bool,
    failures: int,
) -> None:
    row = _source_row({"geolocation_lat": latitude, "geolocation_lng": longitude})
    projected = _single_projection(transformer_connection, row)
    assert projected["geolocation_lat"] == expected_latitude
    assert projected["geolocation_lng"] == expected_longitude
    _assert_flag(projected, outside)
    assert _domain_failures(transformer_connection, row) == failures
    assert _generic_failures(transformer_connection, (row,), FLAG, "not_null") == 0


@pytest.mark.parametrize(
    "source_value",
    [case[1] for case in INVALID_COORDINATES],
    ids=[case[0] for case in INVALID_COORDINATES],
)
@pytest.mark.parametrize("materialized", [True, False], ids=["raw-column", "inline-planner"])
def test_invalid_nonfinite_or_unrepresentable_coordinates_are_null_without_cast_errors(
    transformer_connection: psycopg.Connection, source_value: str, materialized: bool
) -> None:
    row = _source_row(dict.fromkeys(COORDINATE_COLUMNS, source_value))
    projected = _single_projection(transformer_connection, row, materialized=materialized)
    assert all(projected[column] is None for column in COORDINATE_COLUMNS)
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 1
    for column in COORDINATE_COLUMNS:
        assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("missing_column", COORDINATE_COLUMNS)
def test_one_invalid_coordinate_does_not_flag_even_when_other_is_outside_brazil(
    transformer_connection: psycopg.Connection, missing_column: str
) -> None:
    fields: dict[str, object] = {"geolocation_lat": "80", "geolocation_lng": "-100"}
    fields[missing_column] = "bad-number"
    row = _source_row(fields)
    projected = _single_projection(transformer_connection, row)
    assert projected[missing_column] is None
    other = "geolocation_lng" if missing_column == "geolocation_lat" else "geolocation_lat"
    assert projected[other] == (-100.0 if other == "geolocation_lng" else 80.0)
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", MANDATORY_SOURCE)
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_each_missing_mandatory_source_value_remains_a_row_and_blocks_acceptance(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("column", ("_load_id", "_source_row"))
def test_missing_lineage_is_retained_and_blocks_domain_and_generic_null_tests(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: None})
    assert _single_projection(transformer_connection, row)[column] is None
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("ordinal", [0, -1])
def test_nonpositive_source_ordinal_is_retained_but_blocks_source_domain(
    transformer_connection: psycopg.Connection, ordinal: int
) -> None:
    row = _source_row({"_source_row": ordinal})
    assert _single_projection(transformer_connection, row)["_source_row"] == ordinal
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("zip_prefix", ["0", "00123", "123"])
def test_literal_short_and_leading_zero_zip_prefixes_are_valid_without_padding(
    transformer_connection: psycopg.Connection, zip_prefix: str
) -> None:
    row = _source_row({"geolocation_zip_code_prefix": zip_prefix})
    projected = _single_projection(transformer_connection, row)
    assert projected["geolocation_zip_code_prefix"] == zip_prefix
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize("zip_prefix", ["123456", " 123", "12a", "１２３"])
def test_invalid_nonempty_zip_prefix_is_literal_and_fails_without_repair(
    transformer_connection: psycopg.Connection, zip_prefix: str
) -> None:
    row = _source_row({"geolocation_zip_code_prefix": zip_prefix})
    projected = _single_projection(transformer_connection, row)
    assert projected["geolocation_zip_code_prefix"] == zip_prefix
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("state", ["sp", " SP", "XX"])
def test_invalid_literal_state_fails_actual_yaml_values_without_case_or_space_repair(
    transformer_connection: psycopg.Connection, state: str
) -> None:
    row = _source_row({"geolocation_state": state})
    assert _single_projection(transformer_connection, row)["geolocation_state"] == state
    assert _domain_failures(transformer_connection, row) == 1
    assert (
        _generic_failures(transformer_connection, (row,), "geolocation_state", "accepted_values")
        == 1
    )


@pytest.mark.parametrize("city", ["  São d'Água\n新しい🙂  ", " \t\n "])
def test_nonempty_city_unicode_apostrophe_and_whitespace_remain_literal(
    transformer_connection: psycopg.Connection, city: str
) -> None:
    row = _source_row({"geolocation_city": city})
    assert _single_projection(transformer_connection, row)["geolocation_city"] == city
    assert _domain_failures(transformer_connection, row) == 0


def test_complete_observation_duplicates_and_repeated_zip_keep_each_unique_lineage(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row(),
        _source_row({"_source_row": 2}),
        _source_row({"_source_row": 3, "geolocation_city": "sao paulo", "geolocation_lat": "-23"}),
    )
    projected = _projection(transformer_connection, rows)
    assert [row["_source_row"] for row in projected] == [1, 2, 3]
    assert [row["geolocation_zip_code_prefix"] for row in projected] == ["00123"] * 3
    assert [row["geolocation_city"] for row in projected] == ["São Paulo", "São Paulo", "sao paulo"]
    assert projected[0]["geolocation_lat"] == projected[1]["geolocation_lat"]
    assert projected[2]["geolocation_lat"] == -23.0
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_geolocation_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == 0
    )
    assert _reconciliation(transformer_connection, rows) == []


@pytest.mark.parametrize("second_load,expected", [(LOAD, 1), (OTHER_LOAD, 0)])
def test_lineage_unique_per_load_allows_same_ordinal_across_snapshots(
    transformer_connection: psycopg.Connection, second_load: UUID, expected: int
) -> None:
    rows = (_source_row(), _source_row({"_load_id": second_load, "geolocation_city": "second"}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_geolocation_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == expected
    )


def test_actual_reconciliation_passes_literal_unicode_nulls_and_real_outlier_flags(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row({"geolocation_city": "  Café d'Água  "}),
        _source_row({"_source_row": 2, "geolocation_lat": "80", "geolocation_lng": "-100"}),
        _source_row({"_source_row": 3, "geolocation_lat": "", "geolocation_lng": "-100"}),
    )
    assert _reconciliation(transformer_connection, rows) == []


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("geolocation_zip_code_prefix", "123"),
        ("geolocation_city", "changed city"),
        ("geolocation_state", "RJ"),
        ("geolocation_lat", -23.5),
        ("geolocation_lng", -46.5),
        (FLAG, True),
    ],
    ids=[
        "zip-zero-loss",
        "city-edit",
        "state-edit",
        "latitude-rounding",
        "longitude-rounding",
        "flag-edit",
    ],
)
def test_actual_reconciliation_blocks_count_preserving_text_coordinate_or_flag_changes(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _reconciliation(
        transformer_connection, (_source_row(),), overrides={column: replacement}
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


@pytest.mark.parametrize(
    "source_copies,stage_mode,expected",
    [
        (1, "empty", [("missing_from_staging", 1)]),
        (2, "distinct", [("missing_from_staging", 1)]),
        (1, "duplicate", [("unexpected_in_staging", 1)]),
    ],
    ids=["row-loss", "exact-duplicate-loss", "extra-staged-duplicate"],
)
def test_actual_reconciliation_detects_count_and_multiplicity_changes_using_except_all(
    transformer_connection: psycopg.Connection,
    source_copies: int,
    stage_mode: str,
    expected: list[tuple[str, int]],
) -> None:
    rows = (_source_row(),) * source_copies
    assert _reconciliation(transformer_connection, rows, stage_mode=stage_mode) == expected
