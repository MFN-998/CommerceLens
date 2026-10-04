"""Opt-in native order-customer checks with bounded read-only typed CTEs.

Render the actual seven-column mapping, singular tests and YAML-configured dbt
generic macros. Literal source fields, addresses and lineage remain unchanged;
parents enforce references without choosing an address or filtering uncovered ZIPs.
No warehouse records, temporary relations or writes are required.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_ORDER_CUSTOMERS_INTEGRATION") != "1",
    reason="Native read-only order-customer SQL checks require explicit opt-in",
)

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
TYPES = ("uuid", "bigint", *("text",) * 5)
TYPE_CODES = (2950, 20, *(25,) * 5)
STATES = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
TARGET_ID = "0" + "a" * 31
IDENTITIES = ("a" * 32, "b" * 32, "c" * 32)
LOCATIONS = (("00123", True), ("123", False), ("888", False), ("0", False))
CUSTOMERS = (
    (LOAD_A, 1, TARGET_ID, "a" * 32, "00123", " São Paulo ", "SP"),
    (LOAD_A, 4294967297, "0" + "b" * 31, "a" * 32, "123", "新しい🙂", "RJ"),
    (LOAD_B, 1, "c" * 32, "a" * 32, "00123", "Café d'Água", "PB"),
    (LOAD_B, 2, "d" * 32, "b" * 32, "888", "são paulo", "SP"),
    (LOAD_B, 3, "e" * 32, "c" * 32, "0", "\t𐍈 city\n", "AC"),
)
SINGULARS = (
    "order_customers_domains",
    "order_customers_source_reconciliation",
    "order_customers_relationships",
)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_customers": "synthetic_customers",
        "dim_customer": "synthetic_identities",
        "dim_location": "synthetic_locations",
        "int_order_customers": "synthetic_projection",
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
    contract = yaml.safe_load(
        (PROJECT / "models/intermediate/int_order_customers.yml").read_text("utf-8")
    )["models"][0]
    assert contract["name"] == "int_order_customers"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(column["name"] for column in contract["columns"]) == COLUMNS
    assert tuple(column["data_type"] for column in contract["columns"]) == TYPES
    column = next(column for column in contract["columns"] if column["name"] == column_name)
    definition = next(
        test
        for test in column["data_tests"]
        if test == name or isinstance(test, dict) and name in test
    )
    arguments = dict(definition[name]["arguments"]) if isinstance(definition, dict) else {}
    if name == "accepted_values":
        assert len(arguments["values"]) == 27 and set(arguments["values"]) == set(STATES)
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name, **arguments
    ).strip()


def _changed_source(column: str, replacement: object) -> tuple[tuple[object, ...], ...]:
    assert column in COLUMNS
    row = list(CUSTOMERS[0])
    row[COLUMNS.index(column)] = replacement
    return (tuple(row), *CUSTOMERS[1:])


def _cte(
    *,
    customers: tuple[tuple[object, ...], ...] = CUSTOMERS,
    identities: tuple[object, ...] = IDENTITIES,
    locations: tuple[tuple[object, ...], ...] = LOCATIONS,
    source_collation: str | None = None,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert source_collation in {None, "C", "POSIX"}
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("customers", COLUMNS, TYPES, customers),
        ("identities", ("customer_unique_id",), ("text",), tuple((v,) for v in identities)),
        ("locations", ("zip_code_prefix", "has_geolocation"), ("text", "boolean"), locations),
    ):
        assert len(rows) <= 8 and all(len(row) == len(columns) for row in rows)
        collate = (
            (' COLLATE "' + source_collation + '"')
            if name == "customers" and source_collation
            else ""
        )
        casts = [kind + (collate if kind == "text" else "") for kind in types]
        if rows:
            value = "(" + ", ".join("%s::" + kind for kind in casts) + ")"
            selection = "values " + ", ".join(value for _ in rows)
            parameters.extend(value for row in rows for value in row)
        else:
            selection = "select " + ", ".join("null::" + kind for kind in casts) + " where false"
        ctes.append(
            "synthetic_"
            + name
            + " ("
            + ", ".join(columns)
            + ") as materialized ("
            + selection
            + ")"
        )
    ctes.append(
        "synthetic_actual as (" + _render("models/intermediate/int_order_customers.sql") + ")"
    )
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                'case when customer_id COLLATE "C"=%s::text COLLATE "C" '
                "then %s::" + kind + " else " + column + " end as " + column
            )
            parameters.extend((TARGET_ID, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += ' where customer_id COLLATE "C" is distinct from %s::text COLLATE "C"'
        parameters.append(TARGET_ID)
    elif mode in {"extra", "duplicate"}:
        added = ["%s::text" if mode == "extra" and c == "customer_id" else c for c in COLUMNS]
        selection += (
            " union all select " + ", ".join(added) + " from synthetic_actual "
            'where customer_id COLLATE "C"=%s::text COLLATE "C"'
        )
        if mode == "extra":
            parameters.append("f" * 32)
        parameters.append(TARGET_ID)
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
            "Order-customer native setup failed; inspect private local configuration.",
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


@pytest.mark.parametrize(
    "source_collation", [None, "POSIX"], ids=["source-default", "source-posix"]
)
def test_exact_source_fields_types_collations_repeat_identity_addresses_and_lineage(
    transformer_connection: psycopg.Connection, source_collation: str | None
) -> None:
    options = {"source_collation": source_collation}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES
    assert Counter(result.fetchall()) == Counter(CUSTOMERS)
    comparisons = " AND ".join(
        "pg_collation_for(a." + column + ") IS NOT DISTINCT FROM pg_collation_for(s." + column + ")"
        for column in COLUMNS[2:]
    )
    assert _query(
        transformer_connection,
        "select count(*), bool_and(" + comparisons + ") from synthetic_actual a "
        "join synthetic_customers s on a._load_id=s._load_id and a._source_row=s._source_row",
        **options,
    ).fetchone() == (5, True)


@pytest.mark.parametrize("filename", SINGULARS)
def test_actual_singular_contracts_accept_repeated_identity_and_false_geography_coverage(
    transformer_connection: psycopg.Connection, filename: str
) -> None:
    assert _singular(transformer_connection, filename) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_null_source_field_is_retained_and_actual_yaml_not_null_blocks_it(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    customers = _changed_source(column, None)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == Counter(customers)
    assert _generic_count(transformer_connection, column, "not_null") == 0
    assert _generic_count(transformer_connection, column, "not_null", customers=customers) == 1
    assert (
        _singular(
            transformer_connection, "order_customers_source_reconciliation", customers=customers
        )
        == []
    )


def test_actual_yaml_unique_blocks_duplicate_customer_id_without_collapsing_source_rows(
    transformer_connection: psycopg.Connection,
) -> None:
    repeated = (LOAD_B, 4, *CUSTOMERS[0][2:])
    customers = (*CUSTOMERS, repeated)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == Counter(customers)
    assert _generic_count(transformer_connection, "customer_id", "unique") == 0
    assert _generic_count(transformer_connection, "customer_id", "unique", customers=customers) == 1
    assert _generic_count(transformer_connection, "customer_id", "unique", mode="duplicate") == 1
    assert (
        _singular(
            transformer_connection, "order_customers_source_reconciliation", customers=customers
        )
        == []
    )


@pytest.mark.parametrize("state", ["sp", " SP ", "ZZ", "ＳＰ"])
def test_yaml_state_domain_keeps_all_27_states_and_rejects_literal_invalid_values(
    transformer_connection: psycopg.Connection, state: str
) -> None:
    customers = _changed_source("customer_state", state)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == Counter(customers)
    assert _generic_count(transformer_connection, "customer_state", "accepted_values") == 0
    assert (
        _generic_count(
            transformer_connection, "customer_state", "accepted_values", customers=customers
        )
        == 1
    )


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("customer_id", "A" * 32),
        ("customer_id", "a" * 31),
        ("customer_id", " " + TARGET_ID),
        ("customer_id", "ａ" * 32),
        ("customer_unique_id", "A" * 32),
        ("customer_unique_id", "a" * 32 + " "),
        ("customer_unique_id", "ａ" * 32),
        ("customer_zip_code_prefix", "１２３"),
        ("customer_zip_code_prefix", "1 2"),
        ("customer_zip_code_prefix", "000123"),
        ("customer_zip_code_prefix", ""),
        ("_source_row", 0),
    ],
)
def test_literal_invalid_identifiers_zip_and_ordinal_remain_visible_and_fail_domains(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    customers = _changed_source(column, replacement)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == Counter(customers)
    assert _singular(transformer_connection, "order_customers_domains", customers=customers)
    assert (
        _singular(
            transformer_connection, "order_customers_source_reconciliation", customers=customers
        )
        == []
    )


@pytest.mark.parametrize(
    "column,replacement",
    list(zip(COLUMNS, (LOAD_B, 2, "f" * 32, "c" * 32, "888", "Changed city", "RJ"), strict=True)),
)
def test_full_source_reconciliation_blocks_each_changed_field_at_constant_row_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection,
        "order_customers_source_reconciliation",
        override=(column, replacement),
    )


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_full_source_reconciliation_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str
) -> None:
    assert _singular(transformer_connection, "order_customers_source_reconciliation", mode=mode)


@pytest.mark.parametrize("parent", ["identity", "zip", "both"])
def test_missing_parent_references_fail_without_conversion_or_source_row_loss(
    transformer_connection: psycopg.Connection, parent: str
) -> None:
    options = {
        "identities": IDENTITIES[1:] if parent in {"identity", "both"} else IDENTITIES,
        "locations": LOCATIONS[1:] if parent in {"zip", "both"} else LOCATIONS,
    }
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == Counter(CUSTOMERS)
    assert _singular(transformer_connection, "order_customers_relationships", **options)
    assert (
        _singular(transformer_connection, "order_customers_source_reconciliation", **options) == []
    )


def test_repeated_parent_keys_cannot_multiply_or_select_customer_addresses(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {"identities": (*IDENTITIES, IDENTITIES[0]), "locations": (*LOCATIONS, LOCATIONS[0])}
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == Counter(CUSTOMERS)
    assert _generic_count(transformer_connection, "customer_id", "unique", **options) == 0
    for filename in SINGULARS:
        assert _singular(transformer_connection, filename, **options) == []


def test_empty_source_keeps_seven_typed_columns_and_all_contracts_pass(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(transformer_connection, "select * from synthetic_actual", customers=())
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES
    assert result.fetchall() == []
    for filename in SINGULARS:
        assert _singular(transformer_connection, filename, customers=()) == []
    for column in COLUMNS:
        assert _generic_count(transformer_connection, column, "not_null", customers=()) == 0
    assert _generic_count(transformer_connection, "customer_id", "unique", customers=()) == 0
    assert (
        _generic_count(transformer_connection, "customer_state", "accepted_values", customers=())
        == 0
    )
