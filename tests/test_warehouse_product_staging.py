"""Exercise actual product model/domain/lineage SQL on synthetic in-memory CTEs.

SQLite's REGEXP and pg_input_is_valid shims exercise projection, flags and small
numeric/domain cases. SQLite does not prove PostgreSQL numeric precision, signed
64-bit boundaries, input representability or EXCEPT ALL; native opt-in acceptance
tests cover those separately. No fixture files are created or removed.
"""

from __future__ import annotations

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
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
)
FLAGS = (
    "is_missing_category",
    "is_missing_name_length",
    "is_missing_description_length",
    "is_missing_photos_qty",
    "is_missing_weight",
    "is_missing_length",
    "is_missing_height",
    "is_missing_width",
    "is_zero_weight",
)
LOAD = "11111111-1111-4111-8111-111111111111"


def product(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(
            COLUMNS,
            (
                LOAD,
                1,
                "a" * 32,
                "categoria",
                "12.0",
                "100.0",
                "2.0",
                "125.5",
                "20.5",
                "10.25",
                "5.5",
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
        (PROJECT / "macros/source_numeric.sql").read_text("utf-8")
    ).module

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "products")
        return "synthetic_products"

    def ref(name: str) -> str:
        assert name == "stg_products"
        return "synthetic_staged"

    return environment.from_string((PROJECT / relative_path).read_text("utf-8")).render(
        source=source,
        ref=ref,
        config=lambda **_: "",
        commercelens_nullable_bigint=macros.commercelens_nullable_bigint,
        commercelens_nullable_double=macros.commercelens_nullable_double,
    )


def sqlite_input_valid(value: str | None, type_name: str) -> int | None:
    """Limited adapter shim, not an independent PostgreSQL casting oracle."""
    if value is None:
        return None
    try:
        number = Decimal(value)
        if not number.is_finite():
            return 0
        if type_name == "numeric":
            return int(-16383 <= number.adjusted() <= 131071 or number == 0)
        assert type_name == "double precision"
        parsed = float(value)
        return int(math.isfinite(parsed) and (parsed != 0 or number == 0))
    except (InvalidOperation, ValueError, OverflowError):
        return 0


def run_sql(
    rows: list[tuple[object, ...]], singular: str | None = None
) -> list[tuple[object, ...]]:
    """Run actual rendered model and optional singular query with bound values."""
    projection = render_sql("models/staging/stg_products.sql")
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    statement = (
        "with synthetic_products ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), synthetic_staged as ("
        + projection
        + ") "
        + (
            "select * from (" + render_sql(singular) + ") as singular_result"
            if singular
            else "select * from synthetic_staged"
        )
    )
    # REGEXP is SQLite's operator spelling; the PostgreSQL SELECT/CASE stays intact.
    statement = statement.replace(" !~ ", " not regexp ").replace(" ~ ", " regexp ")
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
        connection.create_function(
            "trunc", 1, lambda value: None if value is None else math.trunc(value)
        )
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
        if singular is None:
            assert tuple(column[0] for column in result.description) == COLUMNS + FLAGS
        return result.fetchall()
    finally:
        connection.close()


def test_projection_preserves_literal_categories_and_lineage_without_translation_join() -> None:
    rows = [
        product(product_category_name="  São João / café  "),
        product(_source_row=2, product_id="b" * 32, product_category_name="sem_traducao"),
    ]
    projected = run_sql(rows)
    assert [row[:4] for row in projected] == [row[:4] for row in rows]
    assert all(row[11:] == (0,) * 9 for row in projected)
    assert run_sql(rows, "tests/stg_products_source_domains.sql") == []


def test_whitespace_only_category_is_literal_text_not_missing() -> None:
    row = run_sql([product(product_category_name=" \t\n")])[0]
    assert row[3] == " \t\n"
    assert row[11] == 0


@pytest.mark.parametrize("missing", ["", None])
def test_optional_missing_fields_preserve_rows_and_have_independent_flags(missing: object) -> None:
    row = product(**dict.fromkeys(COLUMNS[3:], missing))
    assert run_sql([row]) == [(LOAD, 1, "a" * 32, *(None,) * 8, *(1,) * 8, 0)]
    assert run_sql([row], "tests/stg_products_source_domains.sql") == []


@pytest.mark.parametrize("column", COLUMNS[3:])
def test_each_optional_attribute_has_its_own_missingness_flag(column: str) -> None:
    row = run_sql([product(**{column: ""})])[0]
    assert row[COLUMNS.index(column)] is None
    expected_flags = [0] * 9
    expected_flags[COLUMNS.index(column) - 3] = 1
    assert row[11:] == tuple(expected_flags)


def test_zero_values_are_preserved_and_zero_weight_is_distinct_from_missingness() -> None:
    row = product(**dict.fromkeys(COLUMNS[4:], "0.0"))
    assert run_sql([row]) == [(LOAD, 1, "a" * 32, "categoria", *(0,) * 7, *(0,) * 8, 1)]
    assert run_sql([row], "tests/stg_products_source_domains.sql") == []


@pytest.mark.parametrize("text", ["12", "12.0", "+12.", "1.2e1", " \t12.000\n"])
def test_integral_decimal_and_exponent_syntax_is_accepted(text: str) -> None:
    row = run_sql([product(product_name_lenght=text)])[0]
    assert row[4] == 12
    assert row[12] == 0
    assert (
        run_sql([product(product_name_lenght=text)], "tests/stg_products_source_domains.sql") == []
    )


@pytest.mark.parametrize("column", COLUMNS[4:7])
def test_fractional_integer_text_is_rejected_without_rounding_or_marking_source_missing(
    column: str,
) -> None:
    source = product(**{column: "12.5"})
    row = run_sql([source])[0]
    assert row[COLUMNS.index(column)] is None
    assert row[COLUMNS.index(column) + 8] == 0
    assert run_sql([source], "tests/stg_products_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", COLUMNS[4:])
def test_malformed_nonempty_numeric_text_fails_domain_without_becoming_source_missing(
    column: str,
) -> None:
    source = product(**{column: "bad numeric"})
    row = run_sql([source])[0]
    assert row[COLUMNS.index(column)] is None
    assert row[COLUMNS.index(column) + 8] == 0
    assert run_sql([source], "tests/stg_products_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", COLUMNS[7:])
@pytest.mark.parametrize("text", ["NaN", "Infinity", "1_000"])
def test_non_decimal_float_extensions_fail_source_domain(column: str, text: str) -> None:
    source = product(**{column: text})
    row = run_sql([source])[0]
    assert row[COLUMNS.index(column)] is None
    assert row[COLUMNS.index(column) + 8] == 0
    assert row[-1] == 0
    assert run_sql([source], "tests/stg_products_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", COLUMNS[4:])
def test_negative_numeric_values_remain_typed_and_fail_nonnegative_domain(column: str) -> None:
    source = product(**{column: "-1.0"})
    assert run_sql([source])[0][COLUMNS.index(column)] == -1
    assert run_sql([source], "tests/stg_products_source_domains.sql") == [(1,)]


def test_fractional_physical_measures_are_preserved() -> None:
    source = product(**dict.fromkeys(COLUMNS[7:], "1.25e2"))
    assert run_sql([source])[0][7:11] == (125.0,) * 4
    assert run_sql([source], "tests/stg_products_source_domains.sql") == []


@pytest.mark.parametrize(
    "changes",
    [
        {"product_id": ""},
        {"product_id": None},
        {"product_id": "A" * 32},
        {"_source_row": 0},
        {"_source_row": -1},
        {"_source_row": None},
    ],
)
def test_invalid_id_or_ordinal_is_retained_and_rejected(changes: dict[str, object]) -> None:
    source = product(**changes)
    assert len(run_sql([source])) == 1
    assert run_sql([source], "tests/stg_products_source_domains.sql") == [(1,)]


def test_duplicate_product_rows_and_lineage_are_retained_for_data_test_failure() -> None:
    source = product()
    projected = run_sql([source, source])
    assert len(projected) == 2
    assert projected[0] == projected[1]
    assert run_sql([source, source], "tests/stg_products_lineage_unique.sql") == [(1,)]


def test_conflicting_product_keys_at_distinct_lineage_are_not_arbitrarily_selected() -> None:
    rows = [product(), product(_source_row=2, product_category_name="different_category")]
    projected = run_sql(rows)
    assert [row[:4] for row in projected] == [row[:4] for row in rows]
    assert run_sql(rows, "tests/stg_products_lineage_unique.sql") == []


def test_lineage_ordinal_is_unique_per_load_not_globally() -> None:
    rows = [
        product(),
        product(_load_id="22222222-2222-4222-8222-222222222222", product_id="b" * 32),
    ]
    assert [row[:3] for row in run_sql(rows)] == [row[:3] for row in rows]
    assert run_sql(rows, "tests/stg_products_lineage_unique.sql") == []
