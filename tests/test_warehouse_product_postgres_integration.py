"""Native product SQL checks against bounded synthetic, read-only VALUES inputs.

Render the real model/macros and the real source-domain singular test. No source
records, fixture tables, temporary relations, or warehouse writes are used.
PostgreSQL rejects float underflow such as 1e-400; Phase 2 pandas instead yields
zero. The warehouse deliberately reports that representability failure.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_PRODUCT_INTEGRATION") != "1",
    reason="Native read-only product SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["products"].columns)
INTEGER_COLUMNS = (
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
)
DOUBLE_COLUMNS = (
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)
MISSING_FLAGS = {
    "product_category_name": "is_missing_category",
    "product_name_lenght": "is_missing_name_length",
    "product_description_lenght": "is_missing_description_length",
    "product_photos_qty": "is_missing_photos_qty",
    "product_weight_g": "is_missing_weight",
    "product_length_cm": "is_missing_length",
    "product_height_cm": "is_missing_height",
    "product_width_cm": "is_missing_width",
}
EXPECTED_COLUMNS = (*SOURCE_COLUMNS, *MISSING_FLAGS.values(), "is_zero_weight")

# Expected values are independent literals; no expected cast invokes a production
# macro or Python's Phase 2 parser. Each named case uses one logical source row.
INTEGER_CASES = (
    ("beyond-binary64-exactness", "9007199254740993.0", 9007199254740993, 0),
    ("signed64-maximum", "9223372036854775807.0", 9223372036854775807, 0),
    ("signed64-minimum-negative-domain", "-9223372036854775808", -9223372036854775808, 1),
    ("above-signed64", "9223372036854775808", None, 1),
    ("below-signed64", "-9223372036854775809", None, 1),
    ("fraction-beyond-float-precision", "1.000000000000000000000000001", None, 1),
    ("extreme-exponent", "1e99999999999999999999999", None, 1),
    ("integral-exponent", "1e2", 100, 0),
    ("plus-decimal-with-whitespace", " \t+42.0\n", 42, 0),
    ("malformed", "bad-number", None, 1),
    ("nan", "NaN", None, 1),
    ("infinity", "Infinity", None, 1),
    ("nonempty-whitespace", " ", None, 1),
    ("zero-is-valid", "0.0", 0, 0),
    ("exact-empty-is-missing", "", None, 0),
)
DOUBLE_CASES = (
    ("decimal-exponent-with-whitespace", " \t+1.25e2\n", 125.0, 0),
    ("negative-preserved-domain-fails", "-2.5", -2.5, 1),
    ("zero-weight-is-valid", "0", 0.0, 0),
    ("exact-empty-is-missing", "", None, 0),
    ("overflow", "1e309", None, 1),
    ("underflow-is-visible-failure", "1e-400", None, 1),
    ("nan", "NaN", None, 1),
    ("infinity", "Infinity", None, 1),
)


def _source_row(changes: dict[str, str]) -> tuple[object, ...]:
    fields = dict.fromkeys(TABLES["products"].columns, "1")
    fields.update(product_id="a" * 32, product_category_name="  Café  ")
    fields.update(changes)
    return (LOAD, 1, *(fields[column] for column in TABLES["products"].columns))


def _case_row(columns: tuple[str, ...], source_value: str) -> tuple[object, ...]:
    changes = dict.fromkeys(columns, source_value)
    if source_value == "":
        changes["product_category_name"] = ""
    return _source_row(changes)


def _render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "products")
        return "synthetic_products"

    def ref(model: str) -> str:
        assert model == "stg_products"
        return "synthetic_projection"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = (PROJECT / "macros/source_numeric.sql").read_text("utf-8")
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _synthetic_cte(*, materialized: bool = True) -> str:
    # MATERIALIZED keeps parameters as column values like the real raw table.
    # Without it, custom-plan constant folding can evaluate unreachable CASTs.
    # Explicit types also keep a synthetic NULL from changing the raw text shape.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in SOURCE_COLUMNS[2:]))
    return (
        "with synthetic_products ("
        + ", ".join(SOURCE_COLUMNS)
        + (") as materialized (values (" if materialized else ") as (values (")
        + ", ".join(placeholders)
        + ")) "
    )


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    # Existing config enforces purpose-specific credentials and verify-full TLS.
    with connect(load_settings(purpose="transformer")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only')"
        ).fetchone() == ("commercelens_transformer", "on")
        yield connection


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    """A failed SQL assertion rolls back its savepoint, preserving later cases."""
    with transformer_connection.transaction():
        yield


def _projection(
    connection: psycopg.Connection, row: tuple[object, ...], *, materialized: bool = True
) -> dict[str, object]:
    statement = (
        _synthetic_cte(materialized=materialized)
        + "select * from ("
        + _render_sql("models/staging/stg_products.sql")
        + ") as projected"
    )
    result = connection.execute(statement, row)
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == EXPECTED_COLUMNS
    records = result.fetchall()
    assert len(records) == 1
    return dict(zip(names, records[0], strict=True))


def _domain_failures(connection: psycopg.Connection, row: tuple[object, ...]) -> int:
    statement = (
        _synthetic_cte().rstrip()
        + ", synthetic_projection as ("
        + _render_sql("models/staging/stg_products.sql")
        + ") select * from ("
        + _render_sql("tests/stg_products_source_domains.sql")
        + ") as source_domain_result"
    )
    result = connection.execute(statement, row)
    assert result.description is not None
    assert tuple(column.name for column in result.description) == ("invalid_source_value_rows",)
    records = result.fetchall()
    # The actual singular query returns no row for a passing input and an
    # aggregate invalid-row count for a failure; never inspect failure records.
    if not records:
        return 0
    assert len(records) == 1
    return records[0][0]


def _assert_flags(projected: dict[str, object], row: tuple[object, ...]) -> None:
    original = dict(zip(SOURCE_COLUMNS, row, strict=True))
    assert projected["_load_id"] == LOAD
    assert projected["_source_row"] == 1
    assert projected["product_id"] == "a" * 32
    category = original["product_category_name"]
    assert projected["product_category_name"] == (None if category == "" else category)
    for column, flag in MISSING_FLAGS.items():
        assert projected[flag] is (original[column] == "")
    assert projected["is_zero_weight"] is (projected["product_weight_g"] == 0)


@pytest.mark.parametrize(
    ("source_value", "expected", "failure_count"),
    [(value, expected, failures) for _, value, expected, failures in INTEGER_CASES],
    ids=[name for name, _, _, _ in INTEGER_CASES],
)
def test_native_integer_projection_and_real_domain_query(
    transformer_connection: psycopg.Connection,
    source_value: str,
    expected: int | None,
    failure_count: int,
) -> None:
    row = _case_row(INTEGER_COLUMNS, source_value)
    projected = _projection(transformer_connection, row)
    for column in INTEGER_COLUMNS:
        assert projected[column] == expected
        assert projected[column] is None or type(projected[column]) is int
    for column in DOUBLE_COLUMNS:
        assert projected[column] == 1.0
    _assert_flags(projected, row)
    assert _domain_failures(transformer_connection, row) == failure_count


@pytest.mark.parametrize(
    ("source_value", "expected", "failure_count"),
    [(value, expected, failures) for _, value, expected, failures in DOUBLE_CASES],
    ids=[name for name, _, _, _ in DOUBLE_CASES],
)
def test_native_double_projection_and_real_domain_query(
    transformer_connection: psycopg.Connection,
    source_value: str,
    expected: float | None,
    failure_count: int,
) -> None:
    row = _case_row(DOUBLE_COLUMNS, source_value)
    projected = _projection(transformer_connection, row)
    for column in DOUBLE_COLUMNS:
        assert projected[column] == expected
        assert projected[column] is None or type(projected[column]) is float
    for column in INTEGER_COLUMNS:
        assert projected[column] == 1
    _assert_flags(projected, row)
    assert _domain_failures(transformer_connection, row) == failure_count


@pytest.mark.parametrize("column", (*INTEGER_COLUMNS, *DOUBLE_COLUMNS))
def test_each_optional_numeric_column_blocks_invalid_nonempty_input(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    # One independently invalid field catches a missing per-column parse rule
    # even when the other six optional numeric values are valid.
    row = _source_row({column: "bad-number"})
    projected = _projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flags(projected, row)
    assert _domain_failures(transformer_connection, row) == 1


def test_inline_constants_are_guarded_before_immutable_casts(
    transformer_connection: psycopg.Connection,
) -> None:
    # Regression for planning-time evaluation inside an otherwise unused CASE arm.
    row = _source_row(
        dict.fromkeys((*INTEGER_COLUMNS, *DOUBLE_COLUMNS), "1e99999999999999999999999")
    )
    projected = _projection(transformer_connection, row, materialized=False)
    assert all(projected[column] is None for column in (*INTEGER_COLUMNS, *DOUBLE_COLUMNS))
    _assert_flags(projected, row)
