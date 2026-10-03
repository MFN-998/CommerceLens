"""Opt-in read-only checks of actual seller SQL using bounded synthetic CTEs.

Render the model, singular tests and YAML-configured dbt generic macros. No
source records, temporary relations or warehouse writes are required.
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

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_SELLER_DIMENSION_INTEGRATION") != "1",
    reason="Native read-only seller dimension SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
    "has_geolocation",
)
TYPES = ("uuid", "bigint", "text", "text", "text", "text", "boolean")
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
SELLERS = (
    (LOAD_A, 1, "a" * 32, "00123", " São Paulo ", "SP"),
    (LOAD_A, 4294967297, "b" * 32, "00123", "新しい🙂", "RJ"),
    (LOAD_B, 1, "c" * 32, "123", "Café d'Água", "PB"),
    (LOAD_B, 2, "d" * 32, "888", "são paulo", "SP"),
)
LOCATIONS = (("00123", True), ("123", False), ("888", False))
GEOGRAPHY = ("00123", "00123")  # Multiple observations never multiply sellers.
SINGULARS = ("seller_dimension_domains", "seller_dimension_source_reconciliation")


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_sellers": "synthetic_sellers",
        "stg_geolocation": "synthetic_geolocation",
        "dim_location": "synthetic_location",
        "dim_seller": "synthetic_projection",
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
    contract = yaml.safe_load((PROJECT / "models/core/dim_seller.yml").read_text("utf-8"))[
        "models"
    ][0]
    tests = next(column for column in contract["columns"] if column["name"] == column_name)[
        "data_tests"
    ]
    configured = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments: dict[str, object] = {}
    if name == "relationships":
        assert isinstance(configured, dict)
        arguments = dict(configured[name]["arguments"])
        assert arguments["to"] == "ref('dim_location')"
        assert arguments["field"] == "zip_code_prefix"
        arguments["to"] = _environment().compile_expression(arguments["to"])(ref=_reference)
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name, **arguments
    ).strip()


def _cte(
    *,
    sellers: tuple[tuple[object, ...], ...] = SELLERS,
    locations: tuple[tuple[object, ...], ...] = LOCATIONS,
    geography: tuple[object, ...] = GEOGRAPHY,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS
    assert override is None or mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("sellers", COLUMNS[:6], TYPES[:6], sellers),
        ("location", ("zip_code_prefix", "has_geolocation"), ("text", "boolean"), locations),
        (
            "geolocation",
            ("geolocation_zip_code_prefix",),
            ("text",),
            tuple((zip_code,) for zip_code in geography),
        ),
    ):
        assert len(rows) <= 8 and all(len(row) == len(columns) for row in rows)
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in types) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in types) + " where false"
        ctes.append("synthetic_" + name + " (" + ", ".join(columns) + ") as (" + selection + ")")
    ctes.append("synthetic_actual as (" + _render("models/core/dim_seller.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                "case when seller_id='"
                + "a" * 32
                + "' then %s::"
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
    target = "seller_id='" + "a" * 32 + "'"
    if mode == "missing":
        selection += " where not (" + target + ")"
    elif mode in {"extra", "duplicate"}:
        added = [
            "'" + "e" * 32 + "'::text" if mode == "extra" and c == "seller_id" else c
            for c in COLUMNS
        ]
        selection += (
            " union all select " + ", ".join(added) + " from synthetic_actual where " + target
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
            "Seller dimension native setup failed; inspect private local configuration.",
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
    return connection.execute(cte + sql, parameters)


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
        connection,
        "select count(*) from (" + _generic_sql(column, name) + ") as checks",
        **options,
    ).fetchone()
    assert row is not None
    return row[0]


def test_source_address_lineage_exact_types_and_shared_zip_without_fanout(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(transformer_connection, "select * from synthetic_projection order by seller_id")
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == (
        2950,
        20,
        25,
        25,
        25,
        25,
        16,
    )
    assert result.fetchall() == [(*row, index < 2) for index, row in enumerate(SELLERS)]


@pytest.mark.parametrize("filename", SINGULARS)
@pytest.mark.parametrize("covered", [True, False], ids=["mixed-coverage", "all-uncovered"])
def test_actual_singular_contracts_accept_retained_rows_and_legitimate_uncovered_locations(
    transformer_connection: psycopg.Connection, filename: str, covered: bool
) -> None:
    locations = LOCATIONS if covered else tuple((zip_code, False) for zip_code, _ in LOCATIONS)
    assert (
        _singular(
            transformer_connection,
            filename,
            locations=locations,
            geography=GEOGRAPHY if covered else (),
        )
        == []
    )


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_yaml_not_null_blocks_each_missing_required_output(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    assert _generic_count(transformer_connection, column, "not_null") == 0
    assert _generic_count(transformer_connection, column, "not_null", override=(column, None)) == 1


def test_actual_yaml_unique_blocks_repeated_seller_key(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _generic_count(transformer_connection, "seller_id", "unique") == 0
    assert _generic_count(transformer_connection, "seller_id", "unique", mode="duplicate") == 1


def test_missing_location_retains_sellers_with_null_coverage_and_fails_required_reference(
    transformer_connection: psycopg.Connection,
) -> None:
    locations = LOCATIONS[1:]
    assert _query(
        transformer_connection,
        "select seller_id, has_geolocation from synthetic_projection order by seller_id",
        locations=locations,
    ).fetchall() == [("a" * 32, None), ("b" * 32, None), ("c" * 32, False), ("d" * 32, False)]
    assert _generic_count(transformer_connection, "seller_zip_code_prefix", "relationships") == 0
    assert (
        _generic_count(
            transformer_connection, "seller_zip_code_prefix", "relationships", locations=locations
        )
        == 2
    )
    assert (
        _generic_count(transformer_connection, "has_geolocation", "not_null", locations=locations)
        == 2
    )
    assert _singular(
        transformer_connection, "seller_dimension_source_reconciliation", locations=locations
    )


def test_duplicate_location_key_fanout_is_visible_and_blocked(
    transformer_connection: psycopg.Connection,
) -> None:
    locations = (*LOCATIONS, LOCATIONS[0])
    assert _query(
        transformer_connection, "select count(*) from synthetic_projection", locations=locations
    ).fetchone() == (6,)
    assert _generic_count(transformer_connection, "seller_id", "unique", locations=locations) == 2
    assert _singular(
        transformer_connection, "seller_dimension_source_reconciliation", locations=locations
    )


@pytest.mark.parametrize(
    "column,replacement",
    list(zip(COLUMNS, (LOAD_B, 2, "e" * 32, "888", "changed", "RJ", False), strict=True)),
)
def test_actual_reconciliation_detects_each_changed_field_at_constant_row_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection,
        "seller_dimension_source_reconciliation",
        override=(column, replacement),
    )


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("seller_id", "BAD"),
        ("seller_zip_code_prefix", "１２３"),
        ("seller_state", "sp"),
        ("_source_row", 0),
    ],
)
def test_actual_domains_block_invalid_key_zip_state_and_lineage(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "seller_dimension_domains", override=(column, replacement)
    )


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_actual_reconciliation_blocks_source_row_loss_extra_rows_and_duplicate_rows(
    transformer_connection: psycopg.Connection, mode: str
) -> None:
    assert _singular(transformer_connection, "seller_dimension_source_reconciliation", mode=mode)


def test_null_upstream_location_coverage_is_retained_and_rejected(
    transformer_connection: psycopg.Connection,
) -> None:
    locations = (("00123", None), *LOCATIONS[1:])
    assert _query(
        transformer_connection,
        "select count(*) from synthetic_projection where has_geolocation is null",
        locations=locations,
    ).fetchone() == (2,)
    assert (
        _generic_count(transformer_connection, "has_geolocation", "not_null", locations=locations)
        == 2
    )
    assert _singular(
        transformer_connection, "seller_dimension_source_reconciliation", locations=locations
    )
