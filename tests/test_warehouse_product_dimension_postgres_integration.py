"""Opt-in native product dimension checks with bounded read-only typed CTEs.

Render the actual model, singular tests and YAML-configured dbt generic macros.
No source reads, fixture relations or writes are needed. Binary results preserve
exact doubles even when the warehouse session uses extra_float_digits=0.
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
    os.getenv("COMMERCE_WAREHOUSE_PRODUCT_DIMENSION_INTEGRATION") != "1",
    reason="Native read-only product dimension SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
SOURCE_COLUMNS = (
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
COLUMNS = (*SOURCE_COLUMNS, "product_category_name_english", "is_untranslated_category")
SOURCE_TYPES = (
    "uuid",
    "bigint",
    "text",
    "text",
    *("bigint",) * 3,
    *("double precision",) * 4,
    *("boolean",) * 9,
)
TYPES = (*SOURCE_TYPES, "text", "boolean")
MANDATORY = (*COLUMNS[:3], *COLUMNS[11:20], "is_untranslated_category")
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
CATEGORY = " Café "
ENGLISH = "  Coffee ☕  "
TRANSLATION_COLUMNS = (
    "_load_id",
    "_source_row",
    "product_category_name",
    "product_category_name_english",
)
TRANSLATIONS = ((LOAD_A, 1, CATEGORY, ENGLISH), (LOAD_B, 1, "新しい🙂", ENGLISH))
SINGULARS = ("product_dimension_domains", "product_dimension_source_reconciliation")


def _product(letter: str, ordinal: int, category: str | None, **changes: object) -> tuple:
    values = (
        LOAD_A,
        ordinal,
        letter * 32,
        category,
        9007199254740993,
        123,
        2,
        1.2345678901234567,
        2.345678901234567,
        3.456789012345678,
        4.567890123456789,
        *([False] * 9),
    )
    fields = dict(zip(SOURCE_COLUMNS, values, strict=True))
    assert changes.keys() <= fields.keys()
    fields.update(changes)
    return tuple(fields[column] for column in SOURCE_COLUMNS)


PRODUCTS = (
    _product("a", 4294967297, CATEGORY),
    _product(
        "b",
        2,
        None,
        **dict.fromkeys(SOURCE_COLUMNS[4:11]),
        **dict.fromkeys(SOURCE_COLUMNS[11:19], True),
    ),
    _product("c", 3, "untranslated", product_weight_g=0.0, is_zero_weight=True),
    _product("d", 4, "Café"),
    _product("e", 5, " café "),
    _product("f", 6, "新しい🙂", _load_id=LOAD_B),
)
# English spelling and coverage are independent literals, including repeated
# English for distinct keys and valid NULL English for missing/unmapped keys.
EXPECTED = tuple(
    zip(
        PRODUCTS,
        (ENGLISH, None, None, None, None, ENGLISH),
        (False, False, True, True, True, False),
        strict=True,
    )
)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_products": "synthetic_products",
        "stg_category_translation": "synthetic_translation",
        "dim_product": "synthetic_projection",
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
    contract = yaml.safe_load((PROJECT / "models/core/dim_product.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert contract["name"] == "dim_product"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(column["name"] for column in contract["columns"]) == COLUMNS
    column = next(column for column in contract["columns"] if column["name"] == column_name)
    assert name in column["data_tests"]
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
    products: tuple[tuple[object, ...], ...] = PRODUCTS,
    translations: tuple[tuple[object, ...], ...] = TRANSLATIONS,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("products", SOURCE_COLUMNS, SOURCE_TYPES, products),
        ("translation", TRANSLATION_COLUMNS, ("uuid", "bigint", "text", "text"), translations),
    ):
        assert len(rows) <= 8 and all(len(row) == len(columns) for row in rows)
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in types) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in types) + " where false"
        ctes.append(
            "synthetic_"
            + name
            + " ("
            + ", ".join(columns)
            + ") as materialized ("
            + selection
            + ")"
        )
    ctes.append("synthetic_actual as (" + _render("models/core/dim_product.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                'case when product_id COLLATE "C" = %s::text COLLATE "C" '
                "then %s::" + kind + " else " + column + " end as " + column
            )
            parameters.extend(("a" * 32, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += ' where product_id COLLATE "C" is distinct from %s::text COLLATE "C"'
        parameters.append("a" * 32)
    elif mode in {"extra", "duplicate"}:
        added = ["%s::text" if mode == "extra" and c == "product_id" else c for c in COLUMNS]
        selection += (
            " union all select " + ", ".join(added) + " from synthetic_actual "
            'where product_id COLLATE "C" = %s::text COLLATE "C"'
        )
        if mode == "extra":
            parameters.append("0" * 32)
        parameters.append("a" * 32)
    ctes.append("synthetic_projection as (" + selection + ")")
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
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
            "Product dimension native setup failed; inspect private local configuration.",
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
    return connection.execute(cte + sql, parameters, binary=True)


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
        connection, "select count(*) from (" + _generic_sql(column, name) + ") as checks", **options
    ).fetchone()
    assert row is not None
    return row[0]


def test_all_twenty_source_fields_exact_types_optional_nulls_zero_and_literal_lookup(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(transformer_connection, "select * from synthetic_actual order by product_id")
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == (
        2950,
        20,
        25,
        25,
        20,
        20,
        20,
        701,
        701,
        701,
        701,
        *(16,) * 9,
        25,
        16,
    )
    assert result.fetchall() == [
        (*row, english, untranslated) for row, english, untranslated in EXPECTED
    ]


@pytest.mark.parametrize("filename", SINGULARS)
def test_actual_singular_contracts_accept_missing_untranslated_and_repeated_english(
    transformer_connection: psycopg.Connection, filename: str
) -> None:
    assert _singular(transformer_connection, filename) == []


@pytest.mark.parametrize("column", MANDATORY)
def test_yaml_not_null_blocks_each_missing_lineage_id_or_required_flag(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    assert _generic_count(transformer_connection, column, "not_null") == 0
    assert _generic_count(transformer_connection, column, "not_null", override=(column, None)) == 1


def test_yaml_unique_blocks_repeated_dimension_product_id(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _generic_count(transformer_connection, "product_id", "unique") == 0
    assert _generic_count(transformer_connection, "product_id", "unique", mode="duplicate") == 1


@pytest.mark.parametrize("conflicting", [False, True], ids=["identical", "conflicting"])
def test_duplicate_literal_lookup_keys_expose_fanout_and_fail_unique_and_conservation(
    transformer_connection: psycopg.Connection, conflicting: bool
) -> None:
    extra = (LOAD_B, 2, CATEGORY, "Different" if conflicting else ENGLISH)
    translations = (*TRANSLATIONS, extra)
    assert _query(
        transformer_connection, "select count(*) from synthetic_actual", translations=translations
    ).fetchone() == (7,)
    assert (
        _generic_count(transformer_connection, "product_id", "unique", translations=translations)
        == 1
    )
    assert _singular(
        transformer_connection, "product_dimension_source_reconciliation", translations=translations
    )


def test_matched_key_with_null_english_retains_product_and_fails_coverage_domain(
    transformer_connection: psycopg.Connection,
) -> None:
    translations = ((LOAD_A, 1, CATEGORY, None), TRANSLATIONS[1])
    result = _query(
        transformer_connection,
        "select product_category_name_english, is_untranslated_category "
        "from synthetic_actual where product_id=repeat('a',32)",
        translations=translations,
    )
    assert result.fetchone() == (None, False)
    assert _singular(transformer_connection, "product_dimension_domains", translations=translations)


@pytest.mark.parametrize(
    "column,replacement",
    list(
        zip(
            COLUMNS,
            (
                LOAD_B,
                2,
                "0" * 32,
                "changed",
                42,
                43,
                44,
                9.75,
                10.75,
                11.75,
                12.75,
                *([True] * 9),
                "Changed English",
                True,
            ),
            strict=True,
        )
    ),
)
def test_actual_reconciliation_blocks_each_changed_source_field_flag_english_and_coverage(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection,
        "product_dimension_source_reconciliation",
        override=(column, replacement),
    )


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("product_id", "A" * 32),
        ("product_id", " " + "a" * 32),
        ("product_id", "ａ" * 32),
        ("_source_row", 0),
        ("is_missing_category", True),
        ("product_category_name_english", None),
        ("is_untranslated_category", True),
        ("is_untranslated_category", None),
    ],
)
def test_actual_domains_block_invalid_identity_ordinal_and_inconsistent_category_coverage(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "product_dimension_domains", override=(column, replacement)
    )


@pytest.mark.parametrize(
    "category,column,replacement",
    [
        (None, "product_category_name_english", "Invented"),
        (None, "is_untranslated_category", True),
        ("untranslated", "product_category_name_english", "Invented"),
        ("untranslated", "is_untranslated_category", False),
    ],
)
def test_domains_block_labels_or_coverage_that_contradict_missing_and_unmapped_categories(
    transformer_connection: psycopg.Connection,
    category: str | None,
    column: str,
    replacement: object,
) -> None:
    products = (_product("a", 1, category, is_missing_category=category is None),)
    assert _singular(
        transformer_connection,
        "product_dimension_domains",
        products=products,
        override=(column, replacement),
    )


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_actual_reconciliation_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str
) -> None:
    assert _singular(transformer_connection, "product_dimension_source_reconciliation", mode=mode)


def test_empty_input_retains_no_products_and_all_contracts_pass(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _query(
        transformer_connection, "select count(*) from synthetic_actual", products=()
    ).fetchone() == (0,)
    for filename in SINGULARS:
        assert _singular(transformer_connection, filename, products=()) == []
    for column in MANDATORY:
        assert _generic_count(transformer_connection, column, "not_null", products=()) == 0
    assert _generic_count(transformer_connection, "product_id", "unique", products=()) == 0
