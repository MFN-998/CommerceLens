"""Execute actual product dimension/test SQL with query-only synthetic SQLite CTEs.

The YAML-configured generics render installed dbt macros. Python regex and an
occurrence-aware EXCEPT ALL port exercise failure logic, not native PostgreSQL
regex, collation, physical types or double precision comparison acceptance.
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
OTHER_LOAD = "22222222-2222-4222-8222-222222222222"
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
REQUIRED = (*SOURCE_COLUMNS[:3], *SOURCE_COLUMNS[11:], "is_untranslated_category")
TRANSLATION_COLUMNS = (
    "_load_id",
    "_source_row",
    "product_category_name",
    "product_category_name_english",
)
ATTRIBUTES = (10, 20, 2, 5.5, 1.5, 2.5, 3.5)
PRODUCTS = (
    (LOAD, 1, "a" * 32, " café🙂 ", *ATTRIBUTES, *([False] * 9)),
    (LOAD, 2, "b" * 32, "Case", 0, 0, 0, 0.0, 1.0, 2.0, 3.0, *([False] * 8), True),
    (LOAD, 3, "c" * 32, None, *([None] * 7), *([True] * 8), False),
    (
        OTHER_LOAD,
        1,
        "d" * 32,
        "case",
        None,
        40,
        0,
        0.0,
        None,
        5.0,
        None,
        False,
        True,
        False,
        False,
        False,
        True,
        False,
        True,
        True,
    ),
    (OTHER_LOAD, 2, "0123456789abcdef" * 2, "café🙂", *ATTRIBUTES, *([False] * 9)),
)
TRANSLATIONS = (
    (LOAD, 1, " café🙂 ", " Shared English🙂 "),
    (LOAD, 2, "Case", " Shared English🙂 "),
    (OTHER_LOAD, 1, "Unused", "Unused label"),
)
SUBSTITUTIONS = {
    "_load_id": "'22222222-2222-4222-8222-222222222222'",
    "_source_row": "_source_row + 10",
    "product_id": "'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'",
    "product_category_name": "'altered category'",
    **{column: f"coalesce({column}, 0) + 1" for column in SOURCE_COLUMNS[4:11]},
    **{column: "not " + column for column in SOURCE_COLUMNS[11:]},
    "product_category_name_english": "coalesce(product_category_name_english, 'missing') || ' x'",
    "is_untranslated_category": "not is_untranslated_category",
}
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join(
        "'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'" if column == "product_id" else column
        for column in COLUMNS
    )
    + " from projected where product_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
)


def render(relative: str) -> str:
    jinja = pytest.importorskip("jinja2")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        ref=lambda name: name,
        config=config,
    )


def contract() -> dict:
    return pytest.importorskip("yaml").safe_load(
        (PROJECT / "models/core/dim_product.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str, name: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = dict(definition[name]["arguments"]) if isinstance(definition, dict) else {}
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql" / (name + ".sql")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(module, "default__test_" + name)(
        model="dim_product", column_name=column, **arguments
    )


def sqlite_except_all(statement: str) -> str:
    """Port only this singular test's full-row multiset subtraction to SQLite."""

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
            + f" on {matches} and l.occurrence = r.occurrence where r.occurrence is null"
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
    products: tuple[tuple[object, ...], ...] = PRODUCTS,
    translations: tuple[tuple[object, ...], ...] = TRANSLATIONS,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_products", SOURCE_COLUMNS, products),
        ("stg_category_translation", TRANSLATION_COLUMNS, translations),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/dim_product.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"dim_product as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(*generic)
        if generic
        else "select * from dim_product"
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


def test_literal_lookup_preserves_products_nullable_fields_zero_flags_and_lineage() -> None:
    labels = (" Shared English🙂 ", " Shared English🙂 ", None, None, None)
    flags = (False, False, False, True, True)
    expected = [
        (*row, label, flag) for row, label, flag in zip(PRODUCTS, labels, flags, strict=True)
    ]
    assert sorted(run_sql(), key=lambda row: row[2]) == sorted(expected, key=lambda row: row[2])
    assert run_sql("product_dimension_domains") == []
    assert run_sql("product_dimension_source_reconciliation") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
        "uuid",
        "bigint",
        "text",
        "text",
        *(["bigint"] * 3),
        *(["double precision"] * 4),
        *(["boolean"] * 9),
        "text",
        "boolean",
    ]
    for column in REQUIRED:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("product_id", "unique")) == []
    for item in contract()["columns"]:
        if item["name"] not in REQUIRED:
            assert "data_tests" not in item


@pytest.mark.parametrize("column", REQUIRED)
def test_installed_required_generics_reject_each_null_output(column: str) -> None:
    assert run_sql(generic=(column, "not_null"), changes={column: "null"})


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_each_source_field_and_translation_substitution_fails_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("product_dimension_source_reconciliation", changes={column: expression})


@pytest.mark.parametrize(
    "column,expression",
    [
        ("product_id", "null"),
        ("product_id", "''"),
        ("product_id", "'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'"),
        ("product_id", "'gggggggggggggggggggggggggggggggg'"),
        ("product_id", "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"),
        ("product_id", "' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa '"),
        (
            "product_id",
            "'１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１'",
        ),
        ("product_id", "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' || char(10)"),
        ("_source_row", "null"),
        ("_source_row", "0"),
        ("_source_row", "-1"),
    ],
)
def test_dimension_domains_block_invalid_preserved_id_or_ordinal(
    column: str, expression: str
) -> None:
    assert run_sql("product_dimension_domains", changes={column: expression})


@pytest.mark.parametrize(
    "category,english,flag",
    [
        ("null", "'label'", "false"),
        ("null", "null", "true"),
        ("'category'", "null", "false"),
        ("'category'", "'label'", "true"),
        ("'category'", "'label'", "null"),
    ],
)
def test_translation_state_guard_rejects_inconsistent_output(
    category: str, english: str, flag: str
) -> None:
    assert run_sql(
        "product_dimension_domains",
        changes={
            "product_category_name": category,
            "product_category_name_english": english,
            "is_untranslated_category": flag,
        },
    )


def test_removed_lookup_retains_product_as_untranslated_not_missing_category() -> None:
    translations = TRANSLATIONS[1:]
    result = run_sql(translations=translations)
    assert (*PRODUCTS[0], None, True) in result
    assert len(result) == len(PRODUCTS)
    assert run_sql("product_dimension_domains", translations=translations) == []
    assert run_sql("product_dimension_source_reconciliation", translations=translations) == []


def test_null_lookup_key_cannot_translate_missing_source_category() -> None:
    translations = (*TRANSLATIONS, (OTHER_LOAD, 2, None, "Must not match NULL"))
    assert (*PRODUCTS[2], None, False) in run_sql(translations=translations)
    assert run_sql("product_dimension_domains", translations=translations) == []
    assert run_sql("product_dimension_source_reconciliation", translations=translations) == []


def test_null_label_on_matched_lookup_is_retained_and_blocks_translation_consistency() -> None:
    translations = ((*TRANSLATIONS[0][:-1], None), *TRANSLATIONS[1:])
    assert (*PRODUCTS[0], None, False) in run_sql(translations=translations)
    assert run_sql("product_dimension_domains", translations=translations) == [(1,)]
    assert run_sql("product_dimension_source_reconciliation", translations=translations) == []


@pytest.mark.parametrize("label", [TRANSLATIONS[0][-1], "Conflicting literal label"])
def test_identical_or_conflicting_lookup_duplicates_fan_out_and_block_grain(label: str) -> None:
    translations = (*TRANSLATIONS, (OTHER_LOAD, 2, " café🙂 ", label))
    assert len(run_sql(translations=translations)) == 6
    assert run_sql(generic=("product_id", "unique"), translations=translations) == [("a" * 32, 2)]
    assert run_sql("product_dimension_source_reconciliation", translations=translations) == [
        (0, 0, 5, 6)
    ]


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "product_id <> 'dddddddddddddddddddddddddddddddd'"}, (1, 0, 5, 4)),
        ({"suffix": EXTRA_OUTPUT}, (0, 1, 5, 6)),
        (
            {
                "suffix": " union all select * from projected "
                "where product_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
            },
            (0, 1, 5, 6),
        ),
    ],
)
def test_omitted_extra_and_duplicate_products_fail_reconciliation(
    corruption: dict, expected: tuple[int, int, int, int]
) -> None:
    assert run_sql("product_dimension_source_reconciliation", **corruption) == [expected]


def test_empty_product_source_produces_empty_valid_dimension() -> None:
    assert run_sql(products=()) == []
    assert run_sql("product_dimension_domains", products=()) == []
    assert run_sql("product_dimension_source_reconciliation", products=()) == []
    for column in REQUIRED:
        assert run_sql(generic=(column, "not_null"), products=()) == []
    assert run_sql(generic=("product_id", "unique"), products=()) == []


@pytest.mark.parametrize("flag", ["true", "false"])
def test_missing_category_flag_must_describe_the_retained_category(flag: str) -> None:
    assert run_sql("product_dimension_domains", changes={"is_missing_category": flag})
