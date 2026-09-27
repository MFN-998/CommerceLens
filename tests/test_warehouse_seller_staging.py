"""Offline SQL projection checks using only synthetic in-memory VALUES inputs.

SQLite exercises the real portable SELECT/NULLIF projection. PostgreSQL types,
regular expressions, EXCEPT ALL and live dbt tests require separate acceptance.
No files, tables, views, fixtures or other resources are created or removed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
)
LOAD = "11111111-1111-4111-8111-111111111111"


def project_sellers(rows: list[tuple[object, ...]]) -> list[tuple[object, ...]]:
    """Render the actual dbt SELECT against a parameterized read-only CTE."""
    jinja2 = pytest.importorskip("jinja2")

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "sellers")
        return "synthetic_sellers"

    projection = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string((PROJECT / "models/staging/stg_sellers.sql").read_text("utf-8"))
        .render(source=source)
    )
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    statement = (
        "with synthetic_sellers ("
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


def test_projection_preserves_literal_text_and_lineage_without_geography() -> None:
    # No geography relation is provided: sellers require no matching observation.
    rows = [
        (LOAD, 1, "a" * 32, "00123", "São Paulo", "SP"),
        (LOAD, 2, "b" * 32, "7", "  Mixed CASE  ", "RJ"),
        (LOAD, 3, "c" * 32, "00001", "NA", "SP"),
    ]
    assert project_sellers(rows) == rows


def test_exact_empty_text_becomes_null_without_losing_the_source_row() -> None:
    rows = [
        (LOAD, 1, "", "", "", ""),
        (LOAD, 2, None, None, None, None),
        (LOAD, 3, " ", " ", " ", " "),
    ]
    assert project_sellers(rows) == [
        (LOAD, 1, None, None, None, None),
        (LOAD, 2, None, None, None, None),
        (LOAD, 3, " ", " ", " ", " "),
    ]


def test_invalid_values_and_duplicate_source_rows_are_retained_for_data_test_failure() -> None:
    invalid_row = (LOAD, 0, "A" * 32, "12x", "Some City", "xx")
    # SQL must not silently repair/filter invalid keys or conceal grain violations.
    assert project_sellers([invalid_row, invalid_row]) == [invalid_row, invalid_row]


def test_duplicate_seller_ids_do_not_choose_one_address() -> None:
    rows = [
        (LOAD, 1, "a" * 32, "00123", "First City", "SP"),
        (LOAD, 2, "a" * 32, "7", "Other City", "RJ"),
    ]
    assert project_sellers(rows) == rows


def test_source_row_is_preserved_with_its_load_not_assumed_globally_unique() -> None:
    rows = [
        (LOAD, 1, "a" * 32, "00123", "First City", "SP"),
        ("22222222-2222-4222-8222-222222222222", 1, "b" * 32, "7", "Other", "RJ"),
    ]
    assert project_sellers(rows) == rows
