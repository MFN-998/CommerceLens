"""Opt-in, read-only native location SQL checks using bounded synthetic CTEs.

Execute the actual model, singular SQL and YAML-configured generic tests. No
source records, tables, temporary relations or warehouse writes are required.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from importlib.resources import files
from pathlib import Path

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_LOCATION_INTEGRATION") != "1",
    reason="Native read-only location SQL checks require explicit opt-in",
)

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
TYPES = ("text", *("bigint" for _ in range(4)), *("boolean" for _ in range(3)))
CUSTOMERS = ("00123", "123", "0", "777", "00123")
SELLERS = ("00123", "888")
GEOGRAPHY = (
    ("00123", "São Paulo", "SP", False),
    ("00123", "São Paulo", "SP", False),  # Exact duplicate observation counts.
    ("00123", "são Paulo", "SP", True),
    ("00123", "Sao Paulo", "RJ", False),
    ("00123", " São Paulo ", "SP", False),
    ("00123", "São Paulo", "SP", True),
    ("999", "新しい🙂", "SP", False),
)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render(relative_path: str) -> str:
    references = {
        "stg_customers": "synthetic_customers",
        "stg_sellers": "synthetic_sellers",
        "stg_geolocation": "synthetic_geolocation",
        "dim_location": "synthetic_projection",
    }

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        _environment()
        .from_string((PROJECT / relative_path).read_text("utf-8"))
        .render(ref=lambda name: references[name], config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_sql(column_name: str, name: str) -> str:
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/core/dim_location.yml").read_text("utf-8"))[
        "models"
    ][0]
    tests = next(column for column in contract["columns"] if column["name"] == column_name)[
        "data_tests"
    ]
    assert name in tests
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name
    ).strip()


def _cte(
    *,
    customers: tuple[object, ...] = CUSTOMERS,
    sellers: tuple[object, ...] = SELLERS,
    geography: tuple[tuple[object, ...], ...] = GEOGRAPHY,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS
    assert override is None or mode == "same"
    ctes, parameters = [], []
    sources = (
        ("customers", ("customer_zip_code_prefix",), ("text",), tuple((z,) for z in customers)),
        ("sellers", ("seller_zip_code_prefix",), ("text",), tuple((z,) for z in sellers)),
        (
            "geolocation",
            (
                "geolocation_zip_code_prefix",
                "geolocation_city",
                "geolocation_state",
                "is_outside_broad_brazil_bounds",
            ),
            ("text", "text", "text", "boolean"),
            geography,
        ),
    )
    for name, columns, types, rows in sources:
        assert len(rows) <= 12 and all(len(row) == len(columns) for row in rows)
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in types) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in types) + " where false"
        ctes.append("synthetic_" + name + " (" + ", ".join(columns) + ") as (" + selection + ")")
    ctes.append("synthetic_actual as (" + _render("models/core/dim_location.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                "case when zip_code_prefix='00123' then %s::"
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.append(override[1])
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += " where zip_code_prefix <> '00123'"
    elif mode in {"extra", "duplicate"}:
        added = ["'99999'::text" if mode == "extra" else COLUMNS[0], *COLUMNS[1:]]
        selection += (
            " union all select "
            + ", ".join(added)
            + " from synthetic_actual where zip_code_prefix='00123'"
        )
    ctes.append("synthetic_projection as (" + selection + ")")
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
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
            "Location native setup failed; inspect private local configuration.", pytrace=False
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
    return connection.execute(cte + sql, parameters)


def _singular(connection: psycopg.Connection, filename: str, **options: object) -> list[tuple]:
    return _query(
        connection,
        "select * from (" + _render("tests/" + filename + ".sql") + ") as checks",
        **options,
    ).fetchall()


def test_literal_three_source_domain_types_and_duplicate_preserving_evidence(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(
        transformer_connection, "select * from synthetic_projection order by zip_code_prefix"
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == (
        25,
        20,
        20,
        20,
        20,
        16,
        16,
        16,
    )
    assert result.fetchall() == [
        ("0", 0, 0, 0, 0, False, False, False),
        ("00123", 6, 4, 2, 2, True, True, True),
        ("123", 0, 0, 0, 0, False, False, False),
        ("777", 0, 0, 0, 0, False, False, False),
        ("888", 0, 0, 0, 0, False, False, False),
        ("999", 1, 1, 1, 0, True, False, False),
    ]


@pytest.mark.parametrize("copies", [1, 3])
def test_repeated_observations_increase_counts_without_inventing_ambiguity(
    transformer_connection: psycopg.Connection, copies: int
) -> None:
    geography = (("00123", "Café d'Água", "SP", True),) * copies
    assert _query(
        transformer_connection,
        "select * from synthetic_projection where zip_code_prefix='00123'",
        geography=geography,
    ).fetchone() == ("00123", copies, 1, 1, copies, True, False, False)


@pytest.mark.parametrize(
    "geography", [GEOGRAPHY, ()], ids=["covered-and-uncovered", "all-uncovered"]
)
@pytest.mark.parametrize(
    "filename",
    [
        "dim_location_domains",
        "dim_location_source_reconciliation",
        "dim_location_join_conservation",
    ],
)
def test_actual_singular_contracts_accept_retained_rows_and_coverage_gaps(
    transformer_connection: psycopg.Connection,
    geography: tuple[tuple[object, ...], ...],
    filename: str,
) -> None:
    assert _singular(transformer_connection, filename, geography=geography) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_yaml_not_null_blocks_each_corrupt_output_column(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    sql = "select count(*) from (" + _generic_sql(column, "not_null") + ") as checks"
    assert _query(transformer_connection, sql).fetchone() == (0,)
    assert _query(transformer_connection, sql, override=(column, None)).fetchone() == (1,)


def test_actual_yaml_unique_blocks_dimension_fanout(
    transformer_connection: psycopg.Connection,
) -> None:
    sql = "select count(*) from (" + _generic_sql("zip_code_prefix", "unique") + ") as checks"
    assert _query(transformer_connection, sql).fetchone() == (0,)
    assert _query(transformer_connection, sql, mode="duplicate").fetchone() == (1,)


@pytest.mark.parametrize("source", ["customers", "sellers", "geography"])
@pytest.mark.parametrize("zip_value", [None, "", "123456", " 123", "１２３"])
def test_invalid_upstream_zip_stays_visible_and_blocks_domain(
    transformer_connection: psycopg.Connection, source: str, zip_value: str | None
) -> None:
    options = {
        source: ((zip_value, "city", "SP", False),) if source == "geography" else (zip_value,)
    }
    assert _singular(transformer_connection, "dim_location_domains", **options) == [(1, 0, 1)]


@pytest.mark.parametrize("missing_index", [1, 2, 3], ids=["city", "state", "outside-flag"])
def test_mixed_valid_and_null_geography_blocks_instead_of_hiding_nulls_in_aggregates(
    transformer_connection: psycopg.Connection, missing_index: int
) -> None:
    invalid: list[object] = ["00123", "São Paulo", "SP", False]
    invalid[missing_index] = None
    geography = (("00123", "São Paulo", "SP", False), tuple(invalid))
    assert _query(
        transformer_connection,
        "select geolocation_observation_count from synthetic_projection "
        "where zip_code_prefix='00123'",
        geography=geography,
    ).fetchone() == (2,)
    assert _singular(transformer_connection, "dim_location_domains", geography=geography) == [
        (0, 1, 0)
    ]


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("zip_code_prefix", "12x"),
        ("geolocation_observation_count", -1),
        ("geolocation_city_variant_count", -1),
        ("geolocation_state_variant_count", 7),
        ("outside_broad_brazil_observation_count", 7),
        ("geolocation_city_variant_count", 0),
        ("has_geolocation", False),
        ("is_geolocation_city_ambiguous", False),
        ("is_geolocation_state_ambiguous", False),
    ],
)
def test_actual_domains_block_impossible_counters_and_inconsistent_flags(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "dim_location_domains", override=(column, replacement)
    ) == [(0, 0, 1)]


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("zip_code_prefix", "12345"),
        ("geolocation_observation_count", 5),
        ("geolocation_city_variant_count", 3),
        ("geolocation_state_variant_count", 1),
        ("outside_broad_brazil_observation_count", 1),
        ("has_geolocation", False),
        ("is_geolocation_city_ambiguous", False),
        ("is_geolocation_state_ambiguous", False),
    ],
)
def test_actual_reconciliation_detects_every_changed_field_at_constant_row_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "dim_location_source_reconciliation", override=(column, replacement)
    ) == [(1, 1)]


@pytest.mark.parametrize(
    "mode,expected", [("missing", (1, 0)), ("extra", (0, 1)), ("duplicate", (0, 1))]
)
def test_actual_reconciliation_detects_domain_loss_extras_and_duplicate_keys(
    transformer_connection: psycopg.Connection, mode: str, expected: tuple[int, int]
) -> None:
    assert _singular(transformer_connection, "dim_location_source_reconciliation", mode=mode) == [
        expected
    ]


@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_join_conservation_blocks_loss_or_fanout_of_customer_and_seller_rows(
    transformer_connection: psycopg.Connection, mode: str
) -> None:
    assert _singular(transformer_connection, "dim_location_join_conservation", mode=mode) == [(2,)]


def test_join_conservation_blocks_covered_addresses_mislabeled_as_uncovered(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _singular(
        transformer_connection,
        "dim_location_join_conservation",
        override=("has_geolocation", False),
    ) == [(2,)]
