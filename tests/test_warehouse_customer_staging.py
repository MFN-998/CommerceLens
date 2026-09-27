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
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
LOAD = "11111111-1111-4111-8111-111111111111"


def project_customers(rows: list[tuple[object, ...]]) -> list[tuple[object, ...]]:
    """Render the actual dbt SELECT against a parameterized read-only CTE."""
    jinja2 = pytest.importorskip("jinja2")

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "customers")
        return "synthetic_customers"

    projection = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string((PROJECT / "models/staging/stg_customers.sql").read_text("utf-8"))
        .render(source=source)
    )
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    statement = (
        "with synthetic_customers ("
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


def test_projection_preserves_literal_text_repeated_identity_and_lineage() -> None:
    rows = [
        (LOAD, 1, "a" * 32, "1" * 32, "00123", "São Paulo", "SP"),
        (LOAD, 2, "b" * 32, "1" * 32, "7", "  Mixed CASE  ", "RJ"),
        (LOAD, 3, "c" * 32, "2" * 32, "00001", "sao paulo", "SP"),
    ]
    assert project_customers(rows) == rows


def test_exact_empty_text_becomes_null_without_losing_the_source_row() -> None:
    rows = [
        (LOAD, 1, "", "", "", "", ""),
        (LOAD, 2, None, None, None, None, None),
        (LOAD, 3, " ", " ", " ", " ", " "),
    ]
    assert project_customers(rows) == [
        (LOAD, 1, None, None, None, None, None),
        (LOAD, 2, None, None, None, None, None),
        (LOAD, 3, " ", " ", " ", " ", " "),
    ]


def test_invalid_keys_and_duplicate_source_rows_are_retained_for_data_test_failure() -> None:
    invalid_row = (LOAD, 1, "invalid-id", "A" * 32, "12x", "Some City", "xx")
    # SQL must not silently repair/filter invalid keys or conceal grain violations.
    assert project_customers([invalid_row, invalid_row]) == [invalid_row, invalid_row]


def test_source_row_is_preserved_with_its_load_not_assumed_globally_unique() -> None:
    rows = [
        (LOAD, 1, "a" * 32, "1" * 32, "00123", "First City", "SP"),
        ("22222222-2222-4222-8222-222222222222", 1, "b" * 32, "2" * 32, "7", "Other", "RJ"),
    ]
    assert project_customers(rows) == rows
