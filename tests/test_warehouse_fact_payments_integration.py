"""Opt-in aggregate-only physical acceptance of the private payment fact view.

Independent guarded raw expectations conserve all ten fields, source flags and
exact monetary totals. Only metadata/counts/sums leave a read-only transaction;
source records and private connection errors are never exposed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from decimal import Decimal

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_PAYMENTS_INTEGRATION") != "1",
    reason="Built payment-fact checks require explicit opt-in",
)

COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
    "is_zero_installments",
    "is_zero_payment_value",
    "is_undefined_payment_type",
)
TYPES = (
    "uuid",
    "bigint",
    "text",
    "bigint",
    "text",
    "bigint",
    "numeric(18,2)",
    "boolean",
    "boolean",
    "boolean",
)
METHODS = ("credit_card", "boleto", "voucher", "debit_card", "not_defined")
MONEY_MAX = "9999999999999999.99"
DECIMAL_PATTERN = "^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$"


def _fields() -> str:
    return ", ".join(
        (column + ' COLLATE "C"' if column in {"order_id", "payment_type"} else column)
        + " AS "
        + column
        for column in COLUMNS
    )


def _numeric(column: str, *, money: bool = False) -> str:
    pattern = "^[0-9]+([.][0-9]{1,2})?$" if money else DECIMAL_PATTERN
    return (
        f"CAST(CASE WHEN {column} ~ '{pattern}' AND pg_input_is_valid({column}, 'numeric') "
        f"THEN {column} END AS numeric)"
    )


def _valid_bigint(column: str) -> str:
    return (
        f"({column} IS NOT NULL AND {column}=trunc({column}) "
        f"AND {column} BETWEEN -9223372036854775808 AND 9223372036854775807)"
    )


def _source_ctes() -> str:
    normalized = ", ".join(
        column if index < 2 else f"nullif({column}, '') AS {column}"
        for index, column in enumerate(COLUMNS[:7])
    )
    return (
        f"WITH raw_normalized AS MATERIALIZED (SELECT {normalized} FROM raw.order_payments), "
        "raw_numeric AS MATERIALIZED (SELECT *, "
        + _numeric("payment_sequential")
        + " AS sequence_number, "
        + _numeric("payment_installments")
        + " AS installment_number, "
        + _numeric("payment_value", money=True)
        + " AS value_number FROM raw_normalized), "
        "raw_typed AS MATERIALIZED (SELECT _load_id, _source_row, "
        'order_id COLLATE "C" AS order_id, '
        f"CASE WHEN {_valid_bigint('sequence_number')} THEN CAST(sequence_number AS bigint) "
        'END AS payment_sequential, payment_type COLLATE "C" AS payment_type, '
        f"CASE WHEN {_valid_bigint('installment_number')} THEN CAST(installment_number AS bigint) "
        "END AS payment_installments, "
        f"CAST(CASE WHEN value_number<={MONEY_MAX} THEN value_number END AS numeric(18,2)) "
        "AS payment_value FROM raw_numeric), "
        "raw_expected AS MATERIALIZED (SELECT *, "
        "COALESCE(payment_installments=0, false) AS is_zero_installments, "
        "COALESCE(payment_value=0, false) AS is_zero_payment_value, "
        "COALESCE(payment_type COLLATE \"C\"='not_defined', false) AS is_undefined_payment_type "
        "FROM raw_typed), "
        f"staged AS MATERIALIZED (SELECT {_fields()} FROM staging.stg_order_payments), "
        f"actual AS MATERIALIZED (SELECT {_fields()} FROM core.fact_payments) "
    )


def _diagnostic(connection: psycopg.Connection, query: str, params=None):
    try:
        return connection.execute(query, params, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Payment-fact physical query failed; inspect private local configuration.",
            pytrace=False,
        )


@pytest.fixture
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
        ).fetchone() == (
            "commercelens_transformer",
            "on",
        )
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Payment-fact physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def test_payment_fact_restricted_session_types_collations_ownership_and_private_access(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    assert _diagnostic(
        connection,
        "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=session_user",
    ).fetchone() == (True, False, False, False, False, False, False, 2)
    assert _diagnostic(
        connection,
        "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
        "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
        "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user",
    ).fetchall() == [("commercelens_transformer", False, False, True)]
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.order_payments', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.order_payments', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE')",
    ).fetchone() == (True, False, True, False, True, True, True)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='fact_payments'",
    ).fetchone() == ("v", "commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
        "WHERE a.attrelid='core.fact_payments'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(a.atttypid=s.atttypid AND a.atttypmod=s.atttypmod "
        "AND a.attcollation=s.attcollation) FROM pg_attribute a JOIN pg_attribute s "
        "ON s.attrelid='staging.stg_order_payments'::regclass AND s.attname=a.attname "
        "AND s.attnum>0 AND NOT s.attisdropped WHERE a.attrelid='core.fact_payments'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped",
    ).fetchone() == (10, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') "
        "AND NOT has_table_privilege(rolname, 'core.fact_payments', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')",
    ).fetchone() == (4, True)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('fact_payments__dbt_tmp','fact_payments__dbt_backup')",
    ).fetchone() == (0,)


def test_payment_fact_independent_raw_multisets_exact_amount_flags_and_order_membership(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    differences = []
    for left, right in (
        ("raw_expected", "staged"),
        ("staged", "actual"),
        ("raw_expected", "actual"),
    ):
        for expected, observed in ((left, right), (right, left)):
            differences.append(
                f"(SELECT count(*) FROM (SELECT * FROM {expected} EXCEPT ALL "
                f"SELECT * FROM {observed}) differences)"
            )
    rejected = (
        f"(payment_sequential IS NOT NULL AND NOT {_valid_bigint('sequence_number')}) OR "
        f"(payment_installments IS NOT NULL AND NOT {_valid_bigint('installment_number')}) OR "
        f"(payment_value IS NOT NULL AND (value_number IS NULL OR value_number>{MONEY_MAX}))"
    )
    differences.append(f"(SELECT count(*) FROM raw_numeric WHERE {rejected})")
    assert (
        _diagnostic(
            connection,
            _source_ctes() + "SELECT " + ", ".join(differences),
        ).fetchone()
        == (0,) * 7
    )
    summaries = " UNION ALL ".join(
        f"SELECT count(*), (SELECT count(*) FROM (SELECT order_id, payment_sequential "
        f"FROM {relation} GROUP BY order_id, payment_sequential) grain), sum(payment_value), "
        "count(*) FILTER (WHERE is_zero_installments), "
        "count(*) FILTER (WHERE is_zero_payment_value), "
        f"count(*) FILTER (WHERE is_undefined_payment_type) FROM {relation}"
        for relation in ("raw_expected", "staged", "actual")
    )
    assert (
        _diagnostic(connection, _source_ctes() + summaries).fetchall()
        == [(103886, 103886, Decimal("16008872.12"), 2, 9, 3)] * 3
    )
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM core.fact_payments WHERE "
        + " OR ".join(column + " IS NULL" for column in COLUMNS)
        + " OR order_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR _source_row<1 OR payment_sequential<1 OR payment_installments<0 "
        f"OR payment_value<0 OR payment_value>{MONEY_MAX} "
        'OR payment_type COLLATE "C"<>ALL(%s::text[]) '
        "OR is_zero_installments IS DISTINCT FROM COALESCE(payment_installments=0, false) "
        "OR is_zero_payment_value IS DISTINCT FROM COALESCE(payment_value=0, false) "
        "OR is_undefined_payment_type IS DISTINCT FROM "
        "COALESCE(payment_type COLLATE \"C\"='not_defined', false)",
        (list(METHODS),),
    ).fetchone() == (0,)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM core.fact_payments p WHERE NOT EXISTS ("
        'SELECT 1 FROM core.fact_orders o WHERE p.order_id COLLATE "C"=o.order_id COLLATE "C")',
    ).fetchone() == (0,)
