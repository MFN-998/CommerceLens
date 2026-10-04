"""Opt-in native payment-fact checks using bounded read-only typed CTEs.

Actual SQL, singular checks and configured dbt null macros retain split payment
components, exact Decimal amounts, source flags and lineage. All values below
are synthetic; no warehouse records or persistent database objects are used.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_PAYMENTS_INTEGRATION") != "1",
    reason="Native read-only payment-fact SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
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
TYPE_CODES = (2950, 20, 25, 20, 25, 20, 1700, 16, 16, 16)
SINGULARS = (
    "fact_payments_grain",
    "fact_payments_domains",
    "fact_payments_source_reconciliation",
    "fact_payments_relationships",
)
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
TARGET_ID = "a" * 32
ORDER_IDS = (TARGET_ID, "b" * 32, "e" * 32)
PAYMENTS = (
    (LOAD_A, 4294967297, TARGET_ID, 1, "credit_card", 0, Decimal("0.00"), True, True, False),
    (LOAD_A, 2, TARGET_ID, 2, "voucher", 1, Decimal("0.01"), False, False, False),
    (LOAD_A, 3, TARGET_ID, 3, "not_defined", 1, Decimal("0.10"), False, False, True),
    (LOAD_B, 1, ORDER_IDS[1], 1, "boleto", 2, Decimal("0.20"), False, False, False),
    (
        LOAD_B,
        2,
        ORDER_IDS[1],
        2,
        "debit_card",
        9223372036854775807,
        Decimal("9999999999999999.99"),
        False,
        False,
        False,
    ),
    (
        LOAD_B,
        3,
        ORDER_IDS[2],
        9007199254740993,
        "credit_card",
        1,
        Decimal("123.45"),
        False,
        False,
        False,
    ),
)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_order_payments": "synthetic_payments",
        "fact_orders": "synthetic_orders",
        "fact_payments": "synthetic_projection",
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


def _generic_sql(column: str) -> str:
    yaml = pytest.importorskip("yaml")
    model = yaml.safe_load((PROJECT / "models/core/fact_payments.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert model["name"] == "fact_payments"
    assert model["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in model["columns"]) == COLUMNS
    assert tuple(item["data_type"] for item in model["columns"]) == TYPES
    assert all(item["data_tests"] == ["not_null"] for item in model["columns"])
    assert column in COLUMNS
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql/not_null.sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return module.default__test_not_null(model="synthetic_projection", column_name=column).strip()


def _changed(column: str, replacement: object):
    row = list(PAYMENTS[0])
    row[COLUMNS.index(column)] = replacement
    return (tuple(row), *PAYMENTS[1:])


def _cte(
    *,
    payments=PAYMENTS,
    orders=ORDER_IDS,
    source_collation: str | None = None,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert source_collation in {None, "C", "POSIX"}
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("payments", COLUMNS, TYPES, payments),
        ("orders", ("order_id",), ("text",), tuple((value,) for value in orders)),
    ):
        assert len(rows) <= 8 and all(len(row) == len(columns) for row in rows)
        collate = ' COLLATE "' + source_collation + '"' if source_collation else ""
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
    ctes.append("synthetic_actual as (" + _render("models/core/fact_payments.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                'case when order_id COLLATE "C"=%s::text COLLATE "C" and payment_sequential=1 '
                "then %s::" + kind + " else " + column + " end as " + column
            )
            parameters.extend((TARGET_ID, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += (
            ' where not (order_id COLLATE "C"=%s::text COLLATE "C" and payment_sequential=1)'
        )
        parameters.append(TARGET_ID)
    elif mode in {"extra", "duplicate"}:
        added = [
            "%s::text" if mode == "extra" and column == "order_id" else column for column in COLUMNS
        ]
        selection += " union all select " + ", ".join(added) + " from synthetic_actual "
        selection += 'where order_id COLLATE "C"=%s::text COLLATE "C" and payment_sequential=1'
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
        ).fetchone() == (
            "commercelens_transformer",
            "on",
        )
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Payment-fact native setup failed; inspect private local configuration.", pytrace=False
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    with transformer_connection.transaction():
        yield


def _query(connection: psycopg.Connection, sql: str, **options: object):
    cte, parameters = _cte(**options)
    try:
        return connection.execute(cte + sql, parameters, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Payment-fact native query failed; inspect private local configuration.", pytrace=False
        )


def _singular(connection: psycopg.Connection, name: str, **options: object):
    assert name in SINGULARS
    return _query(
        connection,
        "select * from (" + _render("tests/" + name + ".sql") + ") diagnostics",
        **options,
    ).fetchall()


def _null_counts(connection: psycopg.Connection, **options: object):
    checks = [
        "(select count(*) from (" + _generic_sql(column) + ") failures)" for column in COLUMNS
    ]
    result = _query(connection, "select " + ", ".join(checks), **options).fetchone()
    return dict(zip(COLUMNS, result, strict=True))


def _assert_shape(result) -> None:
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES
    assert (result.description[6].precision, result.description[6].scale) == (18, 2)


@pytest.mark.parametrize("source_collation", [None, "POSIX"])
def test_actual_projection_retains_split_components_methods_flags_exact_money_and_lineage(
    transformer_connection: psycopg.Connection, source_collation: str | None
) -> None:
    options = {"source_collation": source_collation}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert Counter(result.fetchall()) == Counter(PAYMENTS)
    assert _query(
        transformer_connection,
        "select count(*), sum(payment_value) from synthetic_actual",
        **options,
    ).fetchone() == (6, sum((row[6] for row in PAYMENTS), Decimal("0.00")))
    assert _query(
        transformer_connection,
        "select bool_and(pg_collation_for(a.order_id) IS NOT DISTINCT FROM "
        "pg_collation_for(s.order_id) AND pg_collation_for(a.payment_type) "
        "IS NOT DISTINCT FROM pg_collation_for(s.payment_type)) "
        "from synthetic_actual a join synthetic_payments s "
        'on a.order_id COLLATE "C"=s.order_id COLLATE "C" '
        "and a.payment_sequential=s.payment_sequential",
        **options,
    ).fetchone() == (True,)
    assert _null_counts(transformer_connection, **options) == dict.fromkeys(COLUMNS, 0)
    for name in SINGULARS:
        assert _singular(transformer_connection, name, **options) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_null_source_field_remains_queryable_and_actual_yaml_required_check_blocks_it(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    payments = _changed(column, None)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", payments=payments
        ).fetchall()
    ) == Counter(payments)
    assert _null_counts(transformer_connection, payments=payments)[column] == 1
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", payments=payments)
        == []
    )


def test_duplicate_composite_components_are_retained_and_fail_grain_without_global_sequence_unique(
    transformer_connection: psycopg.Connection,
) -> None:
    payments = (*PAYMENTS, (LOAD_B, 4, *PAYMENTS[0][2:]))
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", payments=payments
        ).fetchall()
    ) == Counter(payments)
    assert _singular(transformer_connection, "fact_payments_grain", payments=payments) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", payments=payments)
        == []
    )


MUTATIONS = (LOAD_B, 1, "f" * 32, 2, "boleto", 1, Decimal("0.01"), False, False, True)


@pytest.mark.parametrize("column,replacement", list(zip(COLUMNS, MUTATIONS, strict=True)))
def test_complete_multiset_reconciliation_blocks_each_changed_field_at_constant_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection,
        "fact_payments_source_reconciliation",
        override=(column, replacement),
    ) == [(6, 6, 1, 1)]


@pytest.mark.parametrize(
    "mode,diagnostics",
    [("missing", (6, 5, 1, 0)), ("extra", (6, 7, 0, 1)), ("duplicate", (6, 7, 0, 1))],
)
def test_complete_multiset_reconciliation_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str, diagnostics: tuple[int, ...]
) -> None:
    assert _singular(transformer_connection, "fact_payments_source_reconciliation", mode=mode) == [
        diagnostics
    ]
    if mode == "duplicate":
        assert _singular(transformer_connection, "fact_payments_grain", mode=mode) == [(1,)]


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("order_id", "A" * 32),
        ("order_id", " " + TARGET_ID),
        ("order_id", "ａ" * 32),
        ("_source_row", 0),
        ("payment_sequential", 0),
        ("payment_installments", -1),
        ("payment_value", Decimal("-0.01")),
        ("payment_type", "Credit_card"),
        ("payment_type", " voucher "),
        ("payment_type", "NOT_DEFINED"),
    ],
)
def test_literal_invalid_source_domains_are_retained_without_normalizing_or_repairing(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    payments = _changed(column, replacement)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", payments=payments
        ).fetchall()
    ) == Counter(payments)
    assert _singular(transformer_connection, "fact_payments_domains", payments=payments) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", payments=payments)
        == []
    )


@pytest.mark.parametrize("column", COLUMNS[7:])
def test_source_warning_flag_inconsistency_is_retained_and_blocked(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    payments = _changed(column, not PAYMENTS[0][COLUMNS.index(column)])
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", payments=payments
        ).fetchall()
    ) == Counter(payments)
    assert _singular(transformer_connection, "fact_payments_domains", payments=payments) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", payments=payments)
        == []
    )


@pytest.mark.parametrize(
    "orders",
    [
        ORDER_IDS[1:],
        (TARGET_ID.upper(), *ORDER_IDS[1:]),
        (" " + TARGET_ID + " ", *ORDER_IDS[1:]),
        ("ａ" * 32, *ORDER_IDS[1:]),
    ],
)
def test_missing_literal_order_parent_blocks_without_joining_filtering_or_component_loss(
    transformer_connection: psycopg.Connection, orders: tuple[str, ...]
) -> None:
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == Counter(PAYMENTS)
    assert _singular(transformer_connection, "fact_payments_relationships", orders=orders) == [(3,)]
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", orders=orders)
        == []
    )


def test_duplicate_parent_order_keys_cannot_multiply_or_collapse_payment_components(
    transformer_connection: psycopg.Connection,
) -> None:
    orders = (*ORDER_IDS, TARGET_ID)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == Counter(PAYMENTS)
    for name in SINGULARS:
        assert _singular(transformer_connection, name, orders=orders) == []


def test_empty_and_all_null_inputs_keep_ten_typed_columns_and_exact_money_typmod(
    transformer_connection: psycopg.Connection,
) -> None:
    empty = _query(transformer_connection, "select * from synthetic_actual", payments=(), orders=())
    _assert_shape(empty)
    assert empty.fetchall() == []
    for name in SINGULARS:
        assert _singular(transformer_connection, name, payments=(), orders=()) == []
    assert _null_counts(transformer_connection, payments=(), orders=()) == dict.fromkeys(COLUMNS, 0)
    payments = ((None,) * len(COLUMNS),)
    result = _query(transformer_connection, "select * from synthetic_actual", payments=payments)
    _assert_shape(result)
    assert result.fetchall() == list(payments)
    assert _null_counts(transformer_connection, payments=payments) == dict.fromkeys(COLUMNS, 1)
    assert _singular(transformer_connection, "fact_payments_domains", payments=payments) == [(1,)]
    assert _singular(transformer_connection, "fact_payments_relationships", payments=payments) == [
        (1,)
    ]
    assert (
        _singular(transformer_connection, "fact_payments_source_reconciliation", payments=payments)
        == []
    )
