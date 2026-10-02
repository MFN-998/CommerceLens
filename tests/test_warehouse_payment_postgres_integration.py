"""Native payment SQL checks using bounded synthetic, read-only VALUES inputs.

Render the actual payment model/macros, singular domain/grain/lineage queries,
and dbt's generic tests. No raw records, fixture tables, temporary relations, or
warehouse writes are used. Independent literals verify payment warnings and exact
Decimal component sums; exhaustive shared-helper boundaries live in item tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_PAYMENT_INTEGRATION") != "1",
    reason="Native read-only payment SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
OTHER_LOAD = UUID("22222222-2222-4222-8222-222222222222")
ORDER_ID = "a" * 32
OTHER_ORDER_ID = "b" * 32
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["order_payments"].columns)
FLAGS = ("is_zero_installments", "is_zero_payment_value", "is_undefined_payment_type")
EXPECTED_COLUMNS = (*SOURCE_COLUMNS, *FLAGS)
METHODS = ("credit_card", "boleto", "voucher", "debit_card", "not_defined")

# Expectations deliberately do not invoke a production macro or source parser.
PAYMENT_CASES = (
    ("credit-card", "credit_card", "1", "0.1", 1, Decimal("0.10"), ()),
    ("boleto", "boleto", "1", "12.34", 1, Decimal("12.34"), ()),
    (
        "voucher-both-zero",
        "voucher",
        "0.0",
        "0.00",
        0,
        Decimal("0.00"),
        ("is_zero_installments", "is_zero_payment_value"),
    ),
    ("debit-card", "debit_card", "2", "0.2", 2, Decimal("0.20"), ()),
    ("undefined-positive", "not_defined", "3", "4.56", 3, Decimal("4.56"), (FLAGS[2],)),
    ("undefined-both-zero", "not_defined", "0", "0", 0, Decimal("0.00"), FLAGS),
    ("zero-installments", "credit_card", "0", "12.34", 0, Decimal("12.34"), (FLAGS[0],)),
    ("zero-value", "voucher", "1", "0.0", 1, Decimal("0.00"), (FLAGS[1],)),
)
INVALID_NUMERIC_CASES = (
    ("zero-sequence", {"payment_sequential": "0"}, {"payment_sequential": 0}, ()),
    ("negative-sequence", {"payment_sequential": "-1"}, {"payment_sequential": -1}, ()),
    ("fractional-sequence", {"payment_sequential": "1.5"}, {"payment_sequential": None}, ()),
    ("negative-installments", {"payment_installments": "-1"}, {"payment_installments": -1}, ()),
    (
        "fractional-installments",
        {"payment_installments": "0.5"},
        {"payment_installments": None},
        (),
    ),
    ("excess-zero-scale", {"payment_value": "0.000"}, {"payment_value": None}, ()),
    ("negative-value", {"payment_value": "-0.01"}, {"payment_value": None}, ()),
    ("money-exponent", {"payment_value": "1e2"}, {"payment_value": None}, ()),
    (
        "undefined-method-still-flags-rejected-values",
        {
            "payment_type": "not_defined",
            "payment_installments": "bad-number",
            "payment_value": "bad-money",
        },
        {"payment_installments": None, "payment_value": None},
        ("is_undefined_payment_type",),
    ),
)


def _source_row(changes: dict[str, object] | None = None) -> tuple[object, ...]:
    fields: dict[str, object] = {
        "_load_id": LOAD,
        "_source_row": 1,
        "order_id": ORDER_ID,
        "payment_sequential": "1",
        "payment_type": "credit_card",
        "payment_installments": "1",
        "payment_value": "0.10",
    }
    fields.update(changes or {})
    return tuple(fields[column] for column in SOURCE_COLUMNS)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_sql(relative_path: str) -> str:
    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_payments")
        return "synthetic_payments"

    def ref(model: str) -> str:
        assert model in {"stg_order_payments", "stg_orders"}
        return "synthetic_projection" if model == "stg_order_payments" else "synthetic_orders"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = "\n".join(
        (PROJECT / "macros" / filename).read_text("utf-8")
        for filename in ("source_numeric.sql", "source_money.sql")
    )
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        _environment()
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_test_sql(name: str, **arguments: object) -> str:
    # Execute installed dbt generic SQL with only fixture relation names replaced.
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", **arguments
    ).strip()


def _synthetic_cte(
    rows: tuple[tuple[object, ...], ...],
    *,
    materialized: bool = True,
    duplicate_parents: bool = False,
) -> tuple[str, tuple[object, ...]]:
    assert 1 <= len(rows) <= 4
    assert all(len(row) == len(SOURCE_COLUMNS) for row in rows)
    # MATERIALIZED mimics raw text columns. Inline mode probes custom-plan
    # folding of unreachable casts; explicit types preserve synthetic NULL shape.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in SOURCE_COLUMNS[2:]))
    value_row = "(" + ", ".join(placeholders) + ")"
    materialization = "materialized " if materialized else ""
    orders = (ORDER_ID, OTHER_ORDER_ID) * (2 if duplicate_parents else 1)
    ctes = [
        "synthetic_payments ("
        + ", ".join(SOURCE_COLUMNS)
        + ") as "
        + materialization
        + "(values "
        + ", ".join(value_row for _ in rows)
        + ")",
        "synthetic_orders (order_id) as materialized (values "
        + ", ".join("(%s::text)" for _ in orders)
        + ")",
        "synthetic_projection as (" + _render_sql("models/staging/stg_order_payments.sql") + ")",
    ]
    return "with " + ", ".join(ctes) + " ", (*(value for row in rows for value in row), *orders)


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    # Existing purpose-specific configuration enforces transformer credentials/TLS.
    with connect(load_settings(purpose="transformer")) as connection, connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.execute(
            "SELECT session_user, current_user, current_database(), "
            "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
        ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
        connection.execute("SET LOCAL ROLE commercelens_transformer")
        assert connection.execute(
            "SELECT current_user, current_setting('transaction_read_only')"
        ).fetchone() == ("commercelens_transformer", "on")
        yield connection


@pytest.fixture(autouse=True)
def isolated_read_only_case(transformer_connection: psycopg.Connection) -> Iterator[None]:
    """A failing case rolls back its savepoint without poisoning later cases."""
    with transformer_connection.transaction():
        yield


def _projection(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    *,
    materialized: bool = True,
    duplicate_parents: bool = False,
) -> list[dict[str, object]]:
    cte, parameters = _synthetic_cte(
        rows, materialized=materialized, duplicate_parents=duplicate_parents
    )
    result = connection.execute(
        cte
        + "select * from synthetic_projection order by _source_row, order_id, payment_sequential",
        parameters,
    )
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == EXPECTED_COLUMNS
    records = result.fetchall()
    assert len(records) == len(rows)
    return [dict(zip(names, record, strict=True)) for record in records]


def _single_projection(
    connection: psycopg.Connection, row: tuple[object, ...], *, materialized: bool = True
) -> dict[str, object]:
    return _projection(connection, (row,), materialized=materialized)[0]


def _singular_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    filename: str,
    expected_column: str,
) -> int:
    cte, parameters = _synthetic_cte(rows)
    result = connection.execute(
        cte + "select * from (" + _render_sql("tests/" + filename) + ") as singular_result",
        parameters,
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == (expected_column,)
    records = result.fetchall()
    if not records:
        return 0
    assert len(records) == 1
    return records[0][0]


def _domain_failures(connection: psycopg.Connection, row: tuple[object, ...]) -> int:
    return _singular_failures(
        connection, (row,), "stg_order_payments_source_domains.sql", "invalid_source_value_rows"
    )


def _generic_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    name: str,
    **arguments: object,
) -> int:
    cte, parameters = _synthetic_cte(rows)
    result = connection.execute(
        cte
        + "select count(*) from ("
        + _generic_test_sql(name, **arguments)
        + ") as generic_result",
        parameters,
    ).fetchone()
    assert result is not None
    return result[0]


def _assert_flags(projected: dict[str, object], true_flags: tuple[str, ...] = ()) -> None:
    assert all(type(projected[flag]) is bool for flag in FLAGS)
    assert {flag for flag in FLAGS if projected[flag]} == set(true_flags)


@pytest.mark.parametrize(
    "method,installments,amount,expected_installments,expected_amount,true_flags",
    [case[1:] for case in PAYMENT_CASES],
    ids=[case[0] for case in PAYMENT_CASES],
)
def test_literal_methods_and_zero_undefined_warnings_retain_exact_values(
    transformer_connection: psycopg.Connection,
    method: str,
    installments: str,
    amount: str,
    expected_installments: int,
    expected_amount: Decimal,
    true_flags: tuple[str, ...],
) -> None:
    row = _source_row(
        {"payment_type": method, "payment_installments": installments, "payment_value": amount}
    )
    projected = _single_projection(transformer_connection, row)
    assert projected["_load_id"] == LOAD
    assert projected["_source_row"] == 1
    assert projected["order_id"] == ORDER_ID
    assert projected["payment_sequential"] == 1
    assert projected["payment_type"] == method
    assert projected["payment_installments"] == expected_installments
    assert type(projected["payment_installments"]) is int
    assert projected["payment_value"] == expected_amount
    assert type(projected["payment_value"]) is Decimal
    assert projected["payment_value"].as_tuple().exponent == -2
    _assert_flags(projected, true_flags)
    assert _domain_failures(transformer_connection, row) == 0
    assert (
        _generic_failures(
            transformer_connection,
            (row,),
            "accepted_values",
            column_name="payment_type",
            values=METHODS,
        )
        == 0
    )


@pytest.mark.parametrize(
    "changes,expected,true_flags",
    [case[1:] for case in INVALID_NUMERIC_CASES],
    ids=[case[0] for case in INVALID_NUMERIC_CASES],
)
def test_rejected_values_and_negative_domains_do_not_masquerade_as_zero_warnings(
    transformer_connection: psycopg.Connection,
    changes: dict[str, object],
    expected: dict[str, object],
    true_flags: tuple[str, ...],
) -> None:
    row = _source_row(changes)
    projected = _single_projection(transformer_connection, row)
    for column, value in expected.items():
        assert projected[column] == value
    _assert_flags(projected, true_flags)
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", tuple(TABLES["order_payments"].columns))
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_each_mandatory_source_absence_is_retained_and_blocked_with_false_flags(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flags(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), "not_null", column_name=column) == 1


@pytest.mark.parametrize("column", ("_load_id", "_source_row"))
def test_missing_lineage_fails_actual_generic_null_and_source_domain_tests(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: None})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flags(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), "not_null", column_name=column) == 1


@pytest.mark.parametrize("column,source_value", [("_source_row", 0), ("order_id", "A" * 32)])
def test_lineage_ordinal_and_literal_order_id_domains_do_not_repair_source(
    transformer_connection: psycopg.Connection, column: str, source_value: object
) -> None:
    row = _source_row({column: source_value})
    assert _single_projection(transformer_connection, row)[column] == source_value
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("method", ["Credit_Card", " voucher ", "cash"])
def test_case_changed_spaced_or_unknown_methods_fail_actual_dbt_accepted_values(
    transformer_connection: psycopg.Connection, method: str
) -> None:
    row = _source_row({"payment_type": method})
    projected = _single_projection(transformer_connection, row)
    assert projected["payment_type"] == method
    _assert_flags(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert (
        _generic_failures(
            transformer_connection,
            (row,),
            "accepted_values",
            column_name="payment_type",
            values=METHODS,
        )
        == 1
    )


@pytest.mark.parametrize("order_id,expected", [(ORDER_ID, 0), ("d" * 32, 1)])
def test_actual_order_relationship_retains_good_and_missing_reference_components(
    transformer_connection: psycopg.Connection, order_id: str, expected: int
) -> None:
    row = _source_row({"order_id": order_id})
    assert _single_projection(transformer_connection, row)["order_id"] == order_id
    assert _domain_failures(transformer_connection, row) == 0
    assert (
        _generic_failures(
            transformer_connection,
            (row,),
            "relationships",
            column_name="order_id",
            to="synthetic_orders",
            field="order_id",
        )
        == expected
    )


def test_split_components_keep_grain_zero_undefined_rows_and_independent_exact_sums(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row(),
        _source_row({"_source_row": 2, "payment_sequential": "2", "payment_value": "0.2"}),
        _source_row(
            {
                "_source_row": 3,
                "payment_sequential": "3",
                "payment_type": "not_defined",
                "payment_installments": "0",
                "payment_value": "0",
            }
        ),
        _source_row({"_source_row": 4, "order_id": OTHER_ORDER_ID, "payment_value": "12.34"}),
    )
    projected = _projection(transformer_connection, rows, duplicate_parents=True)
    assert [(row["order_id"], row["payment_sequential"]) for row in projected] == [
        (ORDER_ID, 1),
        (ORDER_ID, 2),
        (ORDER_ID, 3),
        (OTHER_ORDER_ID, 1),
    ]
    _assert_flags(projected[2], FLAGS)
    for index in (0, 1, 3):
        _assert_flags(projected[index])
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_payments_grain.sql",
            "duplicate_payment_key_groups",
        )
        == 0
    )
    cte, parameters = _synthetic_cte(rows)
    result = transformer_connection.execute(
        cte
        + "select order_id, count(*), sum(payment_value), "
        + "bool_and(pg_typeof(payment_value)::text = 'numeric') "
        + "from synthetic_projection group by order_id order by order_id",
        parameters,
    ).fetchall()
    assert result == [
        (ORDER_ID, 3, Decimal("0.30"), True),
        (OTHER_ORDER_ID, 1, Decimal("12.34"), True),
    ]
    assert all(type(record[2]) is Decimal for record in result)


def test_duplicate_payment_key_is_retained_but_fails_actual_composite_grain(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (_source_row(), _source_row({"_source_row": 2}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_payments_grain.sql",
            "duplicate_payment_key_groups",
        )
        == 1
    )
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_payments_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == 0
    )


@pytest.mark.parametrize("second_load,expected", [(LOAD, 1), (OTHER_LOAD, 0)])
def test_lineage_uniqueness_is_per_load_and_independent_of_payment_sequence(
    transformer_connection: psycopg.Connection, second_load: UUID, expected: int
) -> None:
    rows = (_source_row(), _source_row({"_load_id": second_load, "payment_sequential": "2"}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_payments_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == expected
    )


def test_inline_invalid_numeric_constants_remain_null_with_only_literal_undefined_warning(
    transformer_connection: psycopg.Connection,
) -> None:
    row = _source_row(
        {
            "payment_sequential": "9223372036854775808",
            "payment_type": "not_defined",
            "payment_installments": "1e99999999999999999999999",
            "payment_value": "0.000",
        }
    )
    projected = _single_projection(transformer_connection, row, materialized=False)
    assert projected["payment_sequential"] is None
    assert projected["payment_installments"] is None
    assert projected["payment_value"] is None
    _assert_flags(projected, ("is_undefined_payment_type",))
