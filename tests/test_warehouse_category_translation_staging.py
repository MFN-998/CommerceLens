"""Offline SQL projection checks using synthetic in-memory VALUES inputs.

SQLite exercises the real portable SELECT/NULLIF projection. PostgreSQL types,
EXCEPT ALL and live dbt tests require separate acceptance. No fixture resources
are created or removed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "product_category_name",
    "product_category_name_english",
)
LOAD = "11111111-1111-4111-8111-111111111111"


def project_categories(rows: list[tuple[object, ...]]) -> list[tuple[object, ...]]:
    """Render the actual dbt SELECT against a parameterized read-only CTE."""
    jinja2 = pytest.importorskip("jinja2")

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "category_translation")
        return "synthetic_categories"

    projection = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string((PROJECT / "models/staging/stg_category_translation.sql").read_text("utf-8"))
        .render(source=source)
    )
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    statement = (
        "with synthetic_categories ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + ") "
        + projection
    )
    parameters = tuple(value for row in rows for value in row)
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("pragma query_only = on")
        result = connection.execute(statement, parameters)
        assert tuple(column[0] for column in result.description) == COLUMNS
        return result.fetchall()
    finally:
        connection.close()


def test_projection_preserves_literal_categories_repeated_english_and_lineage() -> None:
    rows = [
        (LOAD, 1, "São João", "  Same English  "),
        (LOAD, 2, "sao joao", "  Same English  "),
        (LOAD, 3, "  Mixed CASE  ", "Quoted ' text; -- safe"),
        (LOAD, 4, "café", "Coffee\tand\nTea"),
    ]
    assert project_categories(rows) == rows


def test_exact_empty_text_becomes_null_without_losing_the_source_row() -> None:
    rows = [
        (LOAD, 1, "", ""),
        (LOAD, 2, None, None),
        (LOAD, 3, " ", "\t"),
        (LOAD, 4, "sem_traducao", ""),
        (LOAD, 5, "", "Missing original"),
    ]
    assert project_categories(rows) == [
        (LOAD, 1, None, None),
        (LOAD, 2, None, None),
        (LOAD, 3, " ", "\t"),
        (LOAD, 4, "sem_traducao", None),
        (LOAD, 5, None, "Missing original"),
    ]


def test_conflicting_portuguese_keys_are_retained_for_data_test_failure() -> None:
    rows = [
        (LOAD, 1, "repetida", "first translation"),
        (LOAD, 2, "repetida", "second translation"),
    ]
    # A projection must not select an arbitrary translation to conceal bad grain.
    assert project_categories(rows) == rows


def test_duplicate_source_rows_and_invalid_lineage_are_not_filtered_or_repaired() -> None:
    invalid_row = (None, 0, "categoria", "category")
    assert project_categories([invalid_row, invalid_row]) == [invalid_row, invalid_row]


def test_source_row_is_preserved_with_its_load_not_assumed_globally_unique() -> None:
    rows = [
        (LOAD, 1, "categoria_um", "category"),
        ("22222222-2222-4222-8222-222222222222", 1, "categoria_dois", "category"),
    ]
    assert project_categories(rows) == rows
