"""Opt-in read-only checks of actual customer identity SQL with bounded CTEs.

Render the model, singular tests and YAML-configured dbt generic macros. Only
synthetic records are queried; no source reads or temporary relations are needed.
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
    os.getenv("COMMERCE_WAREHOUSE_CUSTOMER_DIMENSION_INTEGRATION") != "1",
    reason="Native read-only customer dimension SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
SOURCE_TYPES = ("uuid", "bigint", "text", "text", "text", "text", "text")
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
IDENTITY_A, IDENTITY_B, IDENTITY_C, IDENTITY_D = (letter * 32 for letter in "abcd")
CUSTOMERS = (
    (LOAD_A, 1, "1" * 32, IDENTITY_A, "00123", " São Paulo ", "SP"),
    (LOAD_A, 4294967297, "2" * 32, IDENTITY_A, "888", "新しい🙂", "RJ"),
    (LOAD_B, 1, "3" * 32, IDENTITY_A, "123", "Café d'Água", "PB"),
    (LOAD_B, 2, "4" * 32, IDENTITY_B, "00123", "são paulo", "SP"),
    (LOAD_B, 3, "5" * 32, IDENTITY_C, "00001", "Other", "AC"),
)
SINGULARS = ("customer_dimension_domains", "customer_dimension_source_reconciliation")


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {"stg_customers": "synthetic_customers", "dim_customer": "synthetic_projection"}[name]


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


def _generic_sql(name: str) -> str:
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/core/dim_customer.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert contract["name"] == "dim_customer"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert len(contract["columns"]) == 1
    column = contract["columns"][0]
    assert (column["name"], column["data_type"]) == ("customer_unique_id", "text")
    assert name in column["data_tests"]
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name="customer_unique_id"
    ).strip()


def _cte(
    *, customers: tuple[tuple[object, ...], ...] = CUSTOMERS, mode: str = "same"
) -> tuple[str, tuple[object, ...]]:
    assert len(customers) <= 8 and all(len(row) == len(SOURCE_COLUMNS) for row in customers)
    assert mode in {"same", "missing", "extra", "changed", "duplicate"}
    parameters: list[object] = []
    if customers:
        value = "(" + ", ".join("%s::" + kind for kind in SOURCE_TYPES) + ")"
        selection = "values " + ", ".join(value for _ in customers)
        parameters.extend(value for row in customers for value in row)
    else:
        selection = "select " + ", ".join("null::" + kind for kind in SOURCE_TYPES) + " where false"
    ctes = [
        "synthetic_customers (" + ", ".join(SOURCE_COLUMNS) + ") as (" + selection + ")",
        "synthetic_actual as (" + _render("models/core/dim_customer.sql") + ")",
    ]
    selection = "select customer_unique_id from synthetic_actual"
    if mode == "missing":
        selection += ' where customer_unique_id is distinct from %s::text collate "C"'
        parameters.append(IDENTITY_A)
    elif mode == "extra":
        selection += ' union all select %s::text collate "C"'
        parameters.append(IDENTITY_D)
    elif mode == "changed":
        selection = (
            'select case when customer_unique_id = %s::text collate "C" '
            'then %s::text collate "C" else customer_unique_id end as customer_unique_id '
            "from synthetic_actual"
        )
        parameters.extend((IDENTITY_A, IDENTITY_D))
    elif mode == "duplicate":
        selection += (
            " union all select customer_unique_id from synthetic_actual "
            'where customer_unique_id = %s::text collate "C"'
        )
        parameters.append(IDENTITY_A)
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
            "Customer dimension native setup failed; inspect private local configuration.",
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


def _generic_count(connection: psycopg.Connection, name: str, **options: object) -> int:
    row = _query(
        connection, "select count(*) from (" + _generic_sql(name) + ") as checks", **options
    ).fetchone()
    assert row is not None
    return row[0]


def test_repeated_identity_across_rows_addresses_and_loads_has_one_text_column(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(
        transformer_connection, "select * from synthetic_actual order by customer_unique_id"
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == ("customer_unique_id",)
    assert tuple(column.type_code for column in result.description) == (25,)
    assert result.fetchall() == [(IDENTITY_A,), (IDENTITY_B,), (IDENTITY_C,)]
    assert _query(
        transformer_connection,
        "select count(*) from synthetic_projection "
        "where pg_collation_for(customer_unique_id) = '\"C\"'",
    ).fetchone() == (3,)


@pytest.mark.parametrize("filename", SINGULARS)
def test_actual_singular_contracts_accept_distinct_source_identities(
    transformer_connection: psycopg.Connection, filename: str
) -> None:
    assert _singular(transformer_connection, filename) == []


@pytest.mark.parametrize("name", ["not_null", "unique"])
def test_actual_yaml_generic_contracts_accept_repeated_upstream_identity(
    transformer_connection: psycopg.Connection, name: str
) -> None:
    assert _generic_count(transformer_connection, name) == 0


@pytest.mark.parametrize(
    "identity",
    [
        "",
        "A" * 32,
        " " + IDENTITY_A,
        IDENTITY_A + " ",
        "ａ" * 32,
        "a" * 31,
        "a" * 33,
        "g" * 32,
        "é" * 32,
        IDENTITY_A + "\n",
    ],
)
def test_invalid_literal_identities_are_retained_and_blocked_without_normalization(
    transformer_connection: psycopg.Connection, identity: str
) -> None:
    customers = (CUSTOMERS[0], (*CUSTOMERS[1][:3], identity, *CUSTOMERS[1][4:]))
    result = _query(
        transformer_connection, "select * from synthetic_projection", customers=customers
    )
    assert set(result.fetchall()) == {(IDENTITY_A,), (identity,)}
    assert _singular(transformer_connection, "customer_dimension_domains", customers=customers) == [
        (1,)
    ]
    assert (
        _singular(
            transformer_connection, "customer_dimension_source_reconciliation", customers=customers
        )
        == []
    )


def test_repeated_null_identity_is_retained_once_and_fails_mandatory_checks(
    transformer_connection: psycopg.Connection,
) -> None:
    customers = (
        CUSTOMERS[0],
        (*CUSTOMERS[1][:3], None, *CUSTOMERS[1][4:]),
        (*CUSTOMERS[2][:3], None, *CUSTOMERS[2][4:]),
    )
    assert _query(
        transformer_connection,
        "select count(*), count(*) filter (where customer_unique_id is null) "
        "from synthetic_projection",
        customers=customers,
    ).fetchone() == (2, 1)
    assert _generic_count(transformer_connection, "not_null", customers=customers) == 1
    assert _singular(transformer_connection, "customer_dimension_domains", customers=customers) == [
        (1,)
    ]
    assert (
        _singular(
            transformer_connection, "customer_dimension_source_reconciliation", customers=customers
        )
        == []
    )


def test_empty_input_stays_empty_and_all_contracts_pass(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _query(
        transformer_connection, "select count(*) from synthetic_projection", customers=()
    ).fetchone() == (0,)
    for filename in SINGULARS:
        assert _singular(transformer_connection, filename, customers=()) == []
    for name in ("not_null", "unique"):
        assert _generic_count(transformer_connection, name, customers=()) == 0


@pytest.mark.parametrize(
    "mode,counts",
    [("missing", (1, 0)), ("extra", (0, 1)), ("changed", (1, 1)), ("duplicate", (0, 1))],
)
def test_actual_reconciliation_blocks_missing_extra_changed_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str, counts: tuple[int, int]
) -> None:
    assert _singular(
        transformer_connection, "customer_dimension_source_reconciliation", mode=mode
    ) == [counts]


def test_actual_yaml_unique_blocks_repeated_dimension_identity(
    transformer_connection: psycopg.Connection,
) -> None:
    assert _generic_count(transformer_connection, "unique", mode="duplicate") == 1


def test_valid_leading_zero_identity_is_preserved_without_casting(
    transformer_connection: psycopg.Connection,
) -> None:
    identity = "0123456789abcdef" * 2
    customers = ((*CUSTOMERS[0][:3], identity, *CUSTOMERS[0][4:]),)
    assert _query(
        transformer_connection, "select * from synthetic_projection", customers=customers
    ).fetchall() == [(identity,)]
    assert (
        _singular(transformer_connection, "customer_dimension_domains", customers=customers) == []
    )
