"""Execute the actual payment-fact SQL with query-only synthetic SQLite CTEs.

Configured generics render installed dbt macros. Regex and occurrence-aware
EXCEPT ALL have bounded SQLite adapters, without proving native PostgreSQL SQL.
Money fixtures use zero and small binary-exact amounts; native PostgreSQL remains
authoritative for exact cents, numeric(18,2), UUIDs, BIGINTs and Boolean types.
No raw parsing, private configuration, datasets, network or fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = "11111111-1111-4111-8111-111111111111"
OTHER_LOAD = "22222222-2222-4222-8222-222222222222"
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
FLAGS = COLUMNS[7:]
PAYMENTS = (
    (LOAD, 1, "a" * 32, 1, "credit_card", 3, 12.5, False, False, False),
    (LOAD, 2, "a" * 32, 2, "voucher", 0, 2.25, True, False, False),
    (OTHER_LOAD, 1, "b" * 32, 1, "boleto", 1, 0.0, False, True, False),
    (OTHER_LOAD, 2, "b" * 32, 2, "debit_card", 1, 0.5, False, False, False),
    (OTHER_LOAD, 3, "b" * 32, 3, "not_defined", 0, 0.0, True, True, True),
)
ORDERS = (("a" * 32,), ("b" * 32,))
SINGULARS = (
    "fact_payments_grain",
    "fact_payments_domains",
    "fact_payments_source_reconciliation",
    "fact_payments_relationships",
)
SUBSTITUTIONS = {
    "_load_id": "'33333333-3333-4333-8333-333333333333'",
    "_source_row": "_source_row + 10",
    "order_id": "'cccccccccccccccccccccccccccccccc'",
    "payment_sequential": "payment_sequential + 10",
    "payment_type": "'changed_method'",
    "payment_installments": "payment_installments + 1",
    "payment_value": "0.25",
    **{column: "not " + column for column in FLAGS},
}
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join("99" if column == "payment_sequential" else column for column in COLUMNS)
    + " from projected where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
    + " and payment_sequential = 1"
)
DUPLICATE_OUTPUT = (
    " union all select * from projected where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
    " and payment_sequential = 2"
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
        (PROJECT / "models/core/fact_payments.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
    definition = next(
        test
        for test in tests
        if test == "not_null" or isinstance(test, dict) and "not_null" in test
    )
    arguments = dict(definition["not_null"]["arguments"]) if isinstance(definition, dict) else {}
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql/not_null.sql"
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return module.default__test_not_null(model="fact_payments", column_name=column, **arguments)


def sqlite_statement(statement: str) -> str:
    """Port only the regex operator and the two bounded full-row EXCEPT ALLs."""
    statement = statement.replace(" !~ ", " not regexp ")

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
    generic: str | None = None,
    *,
    payments: tuple[tuple[object, ...], ...] = PAYMENTS,
    orders: tuple[tuple[object, ...], ...] = ORDERS,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_order_payments", COLUMNS, payments),
        ("fact_orders", ("order_id",), orders),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/fact_payments.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"fact_payments as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(generic)
        if generic
        else "select * from fact_payments"
    )
    statement = sqlite_statement(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    )
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


def test_split_components_all_methods_zeros_and_warnings_preserve_every_source_field() -> None:
    assert sorted(run_sql(), key=lambda row: row[2:4]) == list(PAYMENTS)
    for singular in SINGULARS:
        assert run_sql(singular) == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
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
    ]
    assert sum(len(item["data_tests"]) for item in contract()["columns"]) == 10
    for column in COLUMNS:
        assert run_sql(generic=column) == []


@pytest.mark.parametrize("column", COLUMNS)
def test_each_missing_source_value_remains_visible_and_blocks_required_acceptance(
    column: str,
) -> None:
    row = list(PAYMENTS[0])
    row[COLUMNS.index(column)] = None
    payments = (tuple(row), *PAYMENTS[1:])
    assert Counter(run_sql(payments=payments)) == Counter(payments)
    assert run_sql(generic=column, payments=payments) == [(None,)]
    assert run_sql("fact_payments_domains", payments=payments) == [(1,)]
    assert run_sql("fact_payments_source_reconciliation", payments=payments) == []


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_each_source_lineage_method_amount_or_flag_mutation_fails_full_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("fact_payments_source_reconciliation", changes={column: expression}) == [
        (5, 5, 5, 5)
    ]


@pytest.mark.parametrize("column", FLAGS)
def test_null_output_warning_is_detected_by_required_generic_domain_and_reconciliation(
    column: str,
) -> None:
    assert run_sql(generic=column, changes={column: "null"}) == [(None,)] * 5
    assert run_sql("fact_payments_domains", changes={column: "null"}) == [(5,)]
    assert run_sql("fact_payments_source_reconciliation", changes={column: "null"}) == [
        (5, 5, 5, 5)
    ]


@pytest.mark.parametrize("column", FLAGS)
def test_retained_warning_flags_must_match_their_literal_source_operands(column: str) -> None:
    assert run_sql("fact_payments_domains", changes={column: "not " + column}) == [(5,)]


@pytest.mark.parametrize(
    "order_id",
    [
        "A" * 32,
        "a" * 31,
        "１" * 32,
        "a" * 32 + " ",
        "a" * 32 + "\n",
    ],
)
def test_nonliteral_source_order_key_is_retained_and_blocks_ascii_hex_domain(order_id: str) -> None:
    row = (*PAYMENTS[0][:2], order_id, *PAYMENTS[0][3:])
    assert run_sql(payments=(row,)) == [row]
    assert run_sql("fact_payments_domains", payments=(row,)) == [(1,)]
    assert run_sql("fact_payments_relationships", payments=(row,)) == [(1,)]
    assert run_sql("fact_payments_source_reconciliation", payments=(row,)) == []


@pytest.mark.parametrize("column", ["_source_row", "payment_sequential"])
@pytest.mark.parametrize("expression", ["0", "-1"])
def test_source_and_component_ordinals_must_be_positive(column: str, expression: str) -> None:
    assert run_sql("fact_payments_domains", changes={column: expression}) == [(5,)]


@pytest.mark.parametrize("method", ["Credit_card", "credit_card ", "crédit_card", ""])
def test_unknown_case_space_or_unicode_method_is_retained_and_blocks_literal_domain(
    method: str,
) -> None:
    row = (*PAYMENTS[0][:4], method, *PAYMENTS[0][5:])
    payments = (row,)
    assert run_sql(payments=payments) == [row]
    assert run_sql("fact_payments_domains", payments=payments) == [(1,)]
    assert run_sql("fact_payments_source_reconciliation", payments=payments) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"payment_installments": "-1"},
        {"payment_value": "-0.25"},
        {"payment_value": "1e17"},
    ],
)
def test_negative_installments_amounts_and_clearly_excessive_amount_block_domain(
    changes: dict,
) -> None:
    assert run_sql("fact_payments_domains", changes=changes) == [(5,)]


@pytest.mark.parametrize(
    "duplicate", [PAYMENTS[0], (*PAYMENTS[0][:4], "boleto", 1, 0.5, False, False, False)]
)
def test_identical_or_conflicting_source_composite_duplicate_is_retained_and_blocks_grain(
    duplicate: tuple,
) -> None:
    payments = (*PAYMENTS, duplicate)
    assert Counter(run_sql(payments=payments)) == Counter(payments)
    assert run_sql("fact_payments_grain", payments=payments) == [(1,)]
    assert run_sql("fact_payments_source_reconciliation", payments=payments) == []


@pytest.mark.parametrize(
    "orders,missing",
    [
        ((), 5),
        (ORDERS[1:], 2),
        ((("A" * 32,), ORDERS[1]), 2),
        ((("a" * 32 + " ",), ORDERS[1]), 2),
    ],
)
def test_missing_or_nonliteral_order_membership_fails_without_filtering_payments(
    orders: tuple, missing: int
) -> None:
    assert Counter(run_sql(orders=orders)) == Counter(PAYMENTS)
    assert run_sql("fact_payments_relationships", orders=orders) == [(missing,)]
    assert run_sql("fact_payments_source_reconciliation", orders=orders) == []


def test_duplicate_parent_orders_do_not_fan_out_or_change_payment_projection() -> None:
    orders = (*ORDERS, *ORDERS)
    assert Counter(run_sql(orders=orders)) == Counter(PAYMENTS)
    for singular in SINGULARS:
        assert run_sql(singular, orders=orders) == []


@pytest.mark.parametrize(
    "corruption,diagnostics",
    [
        (
            {
                "predicate": "not (order_id = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "
                "and payment_sequential = 3)"
            },
            (5, 4, 1, 0),
        ),
        ({"suffix": EXTRA_OUTPUT}, (5, 6, 0, 1)),
        ({"suffix": DUPLICATE_OUTPUT}, (5, 6, 0, 1)),
    ],
)
def test_omitted_warning_component_extra_or_duplicate_output_fails_conservation(
    corruption: dict, diagnostics: tuple
) -> None:
    assert run_sql("fact_payments_source_reconciliation", **corruption) == [diagnostics]


def test_count_preserving_component_replacement_with_duplicate_fails_both_multiset_directions() -> (
    None
):
    corruption = {
        "predicate": "not (order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "
        "and payment_sequential = 1)",
        "suffix": DUPLICATE_OUTPUT,
    }
    assert len(run_sql(**corruption)) == len(PAYMENTS)
    assert run_sql("fact_payments_grain", **corruption) == [(1,)]
    assert run_sql("fact_payments_source_reconciliation", **corruption) == [(5, 5, 1, 1)]


def test_empty_relations_produce_an_empty_valid_ten_column_fact() -> None:
    inputs = {"payments": (), "orders": ()}
    assert run_sql(**inputs) == []
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []
    for column in COLUMNS:
        assert run_sql(generic=column, **inputs) == []
