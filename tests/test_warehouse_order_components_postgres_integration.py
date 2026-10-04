"""Opt-in native order-mart checks with bounded read-only typed CTEs.

Actual SQL/configured dbt tests face an independent Python Decimal/group oracle.
Fixtures prove child fanout prevention, missing versus measured zero, literal
keys, parent conservation and aggregate money headroom. No warehouse rows or
objects are read or changed beyond restricted session metadata.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from datetime import date, datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_ORDER_COMPONENTS_INTEGRATION") != "1",
    reason="Native read-only order-component SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
PARENT_COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "is_missing_approval",
    "is_missing_carrier_delivery",
    "is_missing_customer_delivery",
    "is_delivered_missing_approval",
    "is_delivered_missing_carrier_delivery",
    "is_delivered_missing_customer_delivery",
    "is_approval_before_purchase",
    "is_carrier_delivery_before_purchase",
    "is_customer_delivery_before_purchase",
    "is_carrier_delivery_before_approval",
    "is_customer_delivery_before_approval",
    "is_customer_delivery_before_carrier_delivery",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
    "customer_load_id",
    "customer_source_row",
    "purchase_calendar_date",
    "approval_calendar_date",
    "carrier_delivery_calendar_date",
    "customer_delivery_calendar_date",
    "estimated_delivery_calendar_date",
)
DERIVED_COLUMNS = (
    "item_count",
    "source_price_sum",
    "source_freight_sum",
    "shipping_before_purchase_count",
    "shipping_beyond_365_days_count",
    "has_items",
    "payment_count",
    "source_payment_sum",
    "zero_installments_count",
    "zero_payment_value_count",
    "undefined_payment_type_count",
    "has_payments",
    "review_count",
    "answer_before_creation_count",
    "has_reviews",
    "has_multiple_reviews",
)
COLUMNS = (*PARENT_COLUMNS, *DERIVED_COLUMNS)
PARENT_TYPES = (
    "uuid",
    "bigint",
    *("text",) * 3,
    *("timestamp without time zone",) * 5,
    *("boolean",) * 12,
    *("text",) * 4,
    "uuid",
    "bigint",
    *("date",) * 5,
)
DERIVED_TYPES = (
    "bigint",
    "numeric",
    "numeric",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "numeric",
    "bigint",
    "bigint",
    "bigint",
    "boolean",
    "bigint",
    "bigint",
    "boolean",
    "boolean",
)
TYPES = (*PARENT_TYPES, *DERIVED_TYPES)
TYPE_CODES = (
    2950,
    20,
    *(25,) * 3,
    *(1114,) * 5,
    *(16,) * 12,
    *(25,) * 4,
    2950,
    20,
    *(1082,) * 5,
    20,
    1700,
    1700,
    20,
    20,
    16,
    20,
    1700,
    20,
    20,
    20,
    16,
    20,
    20,
    16,
    16,
)
ITEM_COLUMNS = (
    "order_id",
    "price",
    "freight_value",
    "is_shipping_before_purchase",
    "is_shipping_beyond_365_days",
)
PAYMENT_COLUMNS = (
    "order_id",
    "payment_value",
    "is_zero_installments",
    "is_zero_payment_value",
    "is_undefined_payment_type",
)
REVIEW_COLUMNS = ("order_id", "is_answer_before_creation")
SINGULAR_COLUMNS = {
    "order_components_grain": ("duplicate_order_keys",),
    "order_components_domains": ("invalid_order_component_rows",),
    "order_components_orders_reconciliation": (
        "missing_or_changed_count",
        "extra_or_changed_count",
    ),
    "order_components_children_reconciliation": (
        "missing_or_changed_count",
        "extra_or_changed_count",
    ),
}
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
TARGET_ID = "a" * 32
ZERO_ID, MISSING_ID, LARGE_ID = (character * 32 for character in "bcd")
MAX_MONEY = Decimal("9999999999999999.99")


def _parent(identifier: str, ordinal: int, *, missing: bool = False) -> tuple[object, ...]:
    clocks = (
        datetime(2018, 1, 1),
        None if missing else datetime(2018, 1, 1, 1),
        None if missing else datetime(2018, 1, 2),
        None if missing else datetime(2018, 1, 3),
        datetime(2020, 4, 9),
    )
    flags = (missing,) * 6 + (False,) * 6
    return (
        LOAD_A,
        ordinal,
        identifier,
        "e" * 32,
        "delivered",
        *clocks,
        *flags,
        "f" * 32,
        "00123",
        " São Paulo\n𐍈🙂 ",
        "SP",
        LOAD_B,
        ordinal + 1,
        *(clock.date() if clock is not None else None for clock in clocks),
    )


ORDERS = (
    _parent(TARGET_ID, 4294967297),
    _parent(ZERO_ID, 2),
    _parent(MISSING_ID, 3, missing=True),
    _parent(LARGE_ID, 4),
)
ITEMS = (
    (TARGET_ID, Decimal("0.10"), Decimal("1.23"), True, False),
    (TARGET_ID, Decimal("0.20"), Decimal("4.56"), False, True),
    (ZERO_ID, Decimal("0.00"), Decimal("0.00"), False, False),
    (LARGE_ID, MAX_MONEY, MAX_MONEY, True, False),
    (LARGE_ID, MAX_MONEY, MAX_MONEY, False, True),
)
PAYMENTS = (
    (TARGET_ID, Decimal("0.01"), True, False, False),
    (TARGET_ID, Decimal("0.20"), False, False, False),
    (TARGET_ID, Decimal("1.23"), False, False, True),
    (ZERO_ID, Decimal("0.00"), True, True, False),
    (LARGE_ID, MAX_MONEY, False, False, False),
    (LARGE_ID, MAX_MONEY, False, False, False),
)
REVIEWS = ((TARGET_ID, True), (TARGET_ID, False), (ZERO_ID, False))


def _oracle_rows(orders=ORDERS, items=ITEMS, payments=PAYMENTS, reviews=REVIEWS):
    def sums(source, position):
        return sum((row[position] for row in source), Decimal("0.00")) if source else None

    rows = []
    for order in orders:
        identifier = order[2]
        item_rows = [row for row in items if identifier is not None and row[0] == identifier]
        payment_rows = [row for row in payments if identifier is not None and row[0] == identifier]
        review_rows = [row for row in reviews if identifier is not None and row[0] == identifier]
        rows.append(
            (
                *order,
                len(item_rows),
                sums(item_rows, 1),
                sums(item_rows, 2),
                sum(row[3] is True for row in item_rows),
                sum(row[4] is True for row in item_rows),
                bool(item_rows),
                len(payment_rows),
                sums(payment_rows, 1),
                sum(row[2] is True for row in payment_rows),
                sum(row[3] is True for row in payment_rows),
                sum(row[4] is True for row in payment_rows),
                bool(payment_rows),
                len(review_rows),
                sum(row[1] is True for row in review_rows),
                bool(review_rows),
                len(review_rows) > 1,
            )
        )
    return rows


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "fact_orders": "synthetic_orders",
        "fact_order_items": "synthetic_items",
        "fact_payments": "synthetic_payments",
        "fact_reviews": "synthetic_reviews",
        "mart_order_components": "synthetic_projection",
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


def _generic_sql() -> str:
    yaml = pytest.importorskip("yaml")
    model = yaml.safe_load((PROJECT / "models/marts/mart_order_components.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert model["name"] == "mart_order_components"
    assert model["config"] == {"materialized": "view", "schema": "marts"}
    assert tuple(column["name"] for column in model["columns"]) == COLUMNS
    assert tuple(column["data_type"] for column in model["columns"]) == TYPES
    assert [
        (column["name"], column["data_tests"])
        for column in model["columns"]
        if column.get("data_tests")
    ] == [("order_id", ["not_null"])]
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql/not_null.sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return module.default__test_not_null(
        model="synthetic_projection", column_name="order_id"
    ).strip()


def _cte(
    *,
    orders=ORDERS,
    items=ITEMS,
    payments=PAYMENTS,
    reviews=REVIEWS,
    source_collation: str | None = None,
    overrides=None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert source_collation in {None, "C", "POSIX"}
    assert mode in {"same", "missing", "extra", "duplicate", "redistributed"}
    assert overrides is None or set(overrides) <= set(COLUMNS) and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("orders", PARENT_COLUMNS, PARENT_TYPES, orders),
        (
            "items",
            ITEM_COLUMNS,
            ("text", "numeric(18,2)", "numeric(18,2)", "boolean", "boolean"),
            items,
        ),
        (
            "payments",
            PAYMENT_COLUMNS,
            ("text", "numeric(18,2)", "boolean", "boolean", "boolean"),
            payments,
        ),
        ("reviews", REVIEW_COLUMNS, ("text", "boolean"), reviews),
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
    ctes.append("synthetic_actual as (" + _render("models/marts/mart_order_components.sql") + ")")
    oracle = {row[2]: row for row in _oracle_rows(orders, items, payments, reviews)}
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if overrides and column in overrides:
            fields.append(
                'case when order_id COLLATE "C"=%s::text COLLATE "C" then %s::'
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.extend((TARGET_ID, overrides[column]))
        elif mode == "redistributed" and column in DERIVED_COLUMNS:
            position = COLUMNS.index(column)
            fields.append(
                'case when order_id COLLATE "C"=%s::text COLLATE "C" then %s::'
                + kind
                + ' when order_id COLLATE "C"=%s::text COLLATE "C" then %s::'
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.extend(
                (TARGET_ID, oracle[ZERO_ID][position], ZERO_ID, oracle[TARGET_ID][position])
            )
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += ' where order_id COLLATE "C" is distinct from %s::text COLLATE "C"'
        parameters.append(TARGET_ID)
    elif mode in {"extra", "duplicate"}:
        added = [
            "%s::text" if mode == "extra" and column == "order_id" else column for column in COLUMNS
        ]
        selection += " union all select " + ", ".join(added) + " from synthetic_actual "
        selection += 'where order_id COLLATE "C"=%s::text COLLATE "C"'
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
            "Order-mart native setup failed; inspect private local configuration.", pytrace=False
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
            "Order-mart native query failed; inspect private local configuration.", pytrace=False
        )


def _singular(connection: psycopg.Connection, name: str, **options: object):
    assert name in SINGULAR_COLUMNS
    result = _query(
        connection,
        "select * from (" + _render("tests/" + name + ".sql") + ") diagnostics",
        **options,
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == SINGULAR_COLUMNS[name]
    return result.fetchall()


def _null_count(connection: psycopg.Connection, **options: object):
    return _query(
        connection, "select count(*) from (" + _generic_sql() + ") failures", **options
    ).fetchone()[0]


def _assert_shape(result) -> None:
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES
    # SUM(numeric(18,2)) must be unconstrained numeric, including empty outputs.
    for column in ("source_price_sum", "source_freight_sum", "source_payment_sum"):
        field = result.description[COLUMNS.index(column)]
        assert field.precision is None and field.scale is None


@pytest.mark.parametrize("source_collation", [None, "POSIX"])
def test_actual_mart_keeps_49_fields_and_independent_2_by_3_by_2_child_aggregates(
    transformer_connection: psycopg.Connection, source_collation: str | None
) -> None:
    options = {"source_collation": source_collation}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert Counter(result.fetchall()) == Counter(_oracle_rows())
    expected = {row[2]: row[33:] for row in _oracle_rows()}
    assert expected[TARGET_ID] == (
        2,
        Decimal("0.30"),
        Decimal("5.79"),
        1,
        1,
        True,
        3,
        Decimal("1.44"),
        1,
        0,
        1,
        True,
        2,
        1,
        True,
        True,
    )
    assert expected[ZERO_ID][1:3] == (Decimal("0.00"), Decimal("0.00"))
    assert expected[MISSING_ID][1:3] == (None, None)
    assert (
        expected[LARGE_ID][1]
        == expected[LARGE_ID][2]
        == expected[LARGE_ID][7]
        == Decimal("19999999999999999.98")
    )
    equalities = " AND ".join(
        f"pg_collation_for(a.{column}) IS NOT DISTINCT FROM pg_collation_for(o.{column})"
        for column, kind in zip(PARENT_COLUMNS, PARENT_TYPES, strict=True)
        if kind == "text"
    )
    assert _query(
        transformer_connection,
        "select bool_and(" + equalities + ") from synthetic_actual a "
        'join synthetic_orders o on a.order_id COLLATE "C"=o.order_id COLLATE "C"',
        **options,
    ).fetchone() == (True,)
    for name in SINGULAR_COLUMNS:
        assert _singular(transformer_connection, name, **options) == []
    assert _null_count(transformer_connection, **options) == 0


@pytest.mark.parametrize("empty_family", ["children", "all"])
def test_empty_children_and_empty_parents_preserve_typed_shape_and_missingness(
    transformer_connection: psycopg.Connection, empty_family: str
) -> None:
    orders = ORDERS if empty_family == "children" else ()
    options = {"orders": orders, "items": (), "payments": (), "reviews": ()}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert Counter(result.fetchall()) == Counter(_oracle_rows(**options))
    for name in SINGULAR_COLUMNS:
        assert _singular(transformer_connection, name, **options) == []
    assert _null_count(transformer_connection, **options) == 0


def test_orphan_children_cannot_disappear_from_conservation_when_parent_input_is_empty(
    transformer_connection: psycopg.Connection,
) -> None:
    result = _query(transformer_connection, "select * from synthetic_actual", orders=())
    _assert_shape(result)
    assert result.fetchall() == []
    assert (
        _singular(transformer_connection, "order_components_orders_reconciliation", orders=()) == []
    )
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", orders=()
    ) == [(8, 0)]


DERIVED_MUTATIONS = (
    3,
    Decimal("0.31"),
    Decimal("5.80"),
    0,
    0,
    False,
    2,
    Decimal("1.45"),
    0,
    1,
    0,
    False,
    1,
    0,
    False,
    False,
)


@pytest.mark.parametrize(
    "column,replacement", list(zip(DERIVED_COLUMNS, DERIVED_MUTATIONS, strict=True))
)
def test_every_derived_mutation_is_blocked_by_child_conservation_or_presence_domain(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    options = {"overrides": {column: replacement}}
    assert (
        _singular(transformer_connection, "order_components_orders_reconciliation", **options) == []
    )
    children = _singular(
        transformer_connection, "order_components_children_reconciliation", **options
    )
    domains = _singular(transformer_connection, "order_components_domains", **options)
    if column == "has_multiple_reviews":
        assert children == [] and domains == [(1,)]
    else:
        assert children == (
            [(1, 0)] if column in {"has_items", "has_payments", "has_reviews"} else [(1, 1)]
        )


@pytest.mark.parametrize("column", DERIVED_COLUMNS)
def test_null_derived_field_fails_actual_domain_contract(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    assert _singular(
        transformer_connection, "order_components_domains", overrides={column: None}
    ) == [(1,)]


@pytest.mark.parametrize("column", ["source_price_sum", "source_freight_sum", "source_payment_sum"])
@pytest.mark.parametrize(
    "replacement", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-0.01")]
)
def test_nonfinite_or_negative_aggregate_money_fails_without_typmod_rounding(
    transformer_connection: psycopg.Connection, column: str, replacement: Decimal
) -> None:
    options = {"overrides": {column: replacement}}
    assert _singular(transformer_connection, "order_components_domains", **options) == [(1,)]
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", **options
    ) == [(1, 1)]


@pytest.mark.parametrize(
    "overrides",
    [
        {"_load_id": LOAD_B, "_source_row": 1},
        {"customer_id": "9" * 32, "customer_unique_id": "8" * 32},
        {"customer_zip_code_prefix": "123", "customer_city": "São Paulo", "customer_state": "RJ"},
        {
            "order_status": "canceled",
            "order_approved_at": None,
            "is_missing_approval": True,
            "approval_calendar_date": None,
        },
        {
            "purchase_calendar_date": date(2019, 1, 1),
            "order_purchase_timestamp": datetime(2019, 1, 1),
        },
        {"is_approval_before_purchase": True, "is_customer_delivery_before_carrier_delivery": True},
        {"order_id": "f" * 32},
    ],
)
def test_parent_conservation_blocks_changed_lineage_identity_address_lifecycle_dates_and_key(
    transformer_connection: psycopg.Connection, overrides: dict[str, object]
) -> None:
    assert _singular(
        transformer_connection, "order_components_orders_reconciliation", overrides=overrides
    ) == [(1, 1)]


@pytest.mark.parametrize(
    "mode,parents,children",
    [
        ("missing", (1, 0), (3, 0)),
        ("extra", (0, 1), (0, 3)),
        ("duplicate", (0, 1), (0, 3)),
    ],
)
def test_missing_extra_and_duplicate_outputs_fail_complete_reconciliation(
    transformer_connection: psycopg.Connection,
    mode: str,
    parents: tuple[int, int],
    children: tuple[int, int],
) -> None:
    assert _singular(
        transformer_connection, "order_components_orders_reconciliation", mode=mode
    ) == [parents]
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", mode=mode
    ) == [children]
    if mode == "duplicate":
        assert _singular(transformer_connection, "order_components_grain", mode=mode) == [(1,)]


def test_redistribution_between_orders_fails_even_with_unchanged_global_totals_and_valid_domains(
    transformer_connection: psycopg.Connection,
) -> None:
    sums = "select sum(item_count), sum(source_price_sum), sum(source_freight_sum), "
    sums += (
        "sum(payment_count), sum(source_payment_sum), sum(review_count) from synthetic_projection"
    )
    assert (
        _query(transformer_connection, sums, mode="redistributed").fetchone()
        == _query(transformer_connection, sums).fetchone()
    )
    assert _singular(transformer_connection, "order_components_domains", mode="redistributed") == []
    assert (
        _singular(
            transformer_connection, "order_components_orders_reconciliation", mode="redistributed"
        )
        == []
    )
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", mode="redistributed"
    ) == [(6, 6)]


@pytest.mark.parametrize("family", ["items", "payments", "reviews"])
@pytest.mark.parametrize("literal", [TARGET_ID.upper(), " " + TARGET_ID + " ", "ａ" * 32])
def test_child_keys_are_grouped_and_joined_literally_without_case_space_or_unicode_conversion(
    transformer_connection: psycopg.Connection, family: str, literal: str
) -> None:
    sources = {"items": ITEMS, "payments": PAYMENTS, "reviews": REVIEWS}
    rows = sources[family]
    changed = ((literal, *rows[0][1:]), *rows[1:])
    options = {family: changed, "source_collation": "POSIX"}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    assert Counter(result.fetchall()) == Counter(_oracle_rows(**{family: changed}))
    assert (
        _singular(transformer_connection, "order_components_orders_reconciliation", **options) == []
    )
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", **options
    ) == [(1, 0)]


def test_duplicate_parent_keys_are_retained_and_block_grain_and_child_duplication(
    transformer_connection: psycopg.Connection,
) -> None:
    duplicate = (LOAD_B, 1, *ORDERS[0][2:])
    orders = (*ORDERS, duplicate)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == Counter(_oracle_rows(orders=orders))
    assert (
        _singular(transformer_connection, "order_components_orders_reconciliation", orders=orders)
        == []
    )
    assert _singular(transformer_connection, "order_components_grain", orders=orders) == [(1,)]
    assert _singular(
        transformer_connection, "order_components_children_reconciliation", orders=orders
    ) == [(0, 3)]


def test_required_order_id_null_is_retained_and_actual_yaml_macro_blocks_it(
    transformer_connection: psycopg.Connection,
) -> None:
    row = list(ORDERS[0])
    row[2] = None
    orders = (tuple(row), *ORDERS[1:])
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == Counter(_oracle_rows(orders=orders))
    assert _null_count(transformer_connection, orders=orders) == 1
    assert _singular(transformer_connection, "order_components_domains", orders=orders) == [(1,)]
    assert (
        _singular(transformer_connection, "order_components_orders_reconciliation", orders=orders)
        == []
    )
