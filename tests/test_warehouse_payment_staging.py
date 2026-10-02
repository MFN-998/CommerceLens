"""Execute actual payment projection, singular and dbt generic SQL offline.

Bound synthetic VALUES stay in query-only in-memory SQLite. Regex uses an adapter
shim and EXCEPT ALL uses equivalent row-numbered NULL-safe multiset subtraction.
SQLite casts cover small numeric examples only; accepted shared-helper native
tests establish exact precision, signed-64-bit limits and PostgreSQL planner safety.
This suite focuses payment component grain, literal methods and warning flags.
No fixture files or persistent database resources are created or removed.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
)
FLAGS = ("is_zero_installments", "is_zero_payment_value", "is_undefined_payment_type")
EXPECTED_COLUMNS = COLUMNS + FLAGS
METHODS = ("credit_card", "boleto", "voucher", "debit_card", "not_defined")
LOAD = "11111111-1111-4111-8111-111111111111"
ORDER = "a" * 32


def payment(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(COLUMNS, (LOAD, 1, ORDER, "1", "credit_card", "3", "12.34"), strict=True)
    )
    assert set(changes) <= set(values)
    values.update(changes)
    return tuple(values[column] for column in COLUMNS)


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = "\n".join(
        (PROJECT / "macros" / name).read_text("utf-8")
        for name in ("source_numeric.sql", "source_money.sql")
    )

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_payments")
        return "synthetic_order_payments"

    def ref(name: str) -> str:
        assert name == "stg_order_payments"
        return "synthetic_staged"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    return (
        environment.from_string(macros + "\n" + (PROJECT / relative_path).read_text("utf-8"))
        .render(source=source, ref=ref, config=config)
        .strip()
    )


def model_contract() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((PROJECT / "models/staging/stg_order_payments.yml").read_text("utf-8"))[
        "models"
    ][0]


def render_generic(column: str, name: str) -> str:
    """Use installed dbt generic-test SQL with the actual payment YAML arguments."""
    jinja2 = pytest.importorskip("jinja2")
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    path = Path(spec.origin).parent / "macros/generic_test_sql" / f"{name}.sql"
    tests = next(record for record in model_contract()["columns"] if record["name"] == column)[
        "data_tests"
    ]
    definition = next(
        record for record in tests if record == name or isinstance(record, dict) and name in record
    )
    arguments = definition[name]["arguments"].copy() if isinstance(definition, dict) else {}
    if name == "relationships":
        assert arguments == {"to": "ref('stg_orders')", "field": "order_id"}
        arguments["to"] = "synthetic_orders"
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = environment.from_string(path.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(macros, f"default__test_{name}")(
        model="synthetic_staged", column_name=column, **arguments
    )


def sqlite_input_valid(value: str | None, type_name: str) -> int | None:
    """Small-value adapter only; native PostgreSQL is the representability authority."""
    assert type_name == "numeric"
    if value is None:
        return None
    try:
        number = Decimal(value)
        return int(number.is_finite() and (-16383 <= number.adjusted() <= 131071 or number == 0))
    except (InvalidOperation, ValueError, OverflowError):
        return 0


def sqlite_except_all(statement: str) -> str:
    """Replace only adapter-incompatible multiset subtraction, preserving duplicates."""

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        partition = ", ".join(EXPECTED_COLUMNS)
        matches = " and ".join(f"lhs.{column} is rhs.{column}" for column in EXPECTED_COLUMNS)
        return (
            "select "
            + ", ".join("lhs." + column for column in EXPECTED_COLUMNS)
            + " from (select *, row_number() over (partition by "
            + partition
            + ") as occurrence from "
            + left
            + ") lhs left join "
            + "(select *, row_number() over (partition by "
            + partition
            + ") as occurrence from "
            + right
            + ") rhs on "
            + matches
            + " and lhs.occurrence=rhs.occurrence where rhs.occurrence is null"
        )

    return re.sub(
        r"select \* from (expected|actual)\s+except all\s+select \* from (expected|actual)",
        subtract,
        statement,
        flags=re.IGNORECASE,
    )


def run_sql(
    rows: list[tuple[object, ...]],
    singular: str | None = None,
    generic: tuple[str, str] | None = None,
    *,
    changes: dict[str, str] | None = None,
    staged_filter: str = "true",
    staged_suffix: str = "",
    parent: str | None = ORDER,
) -> list[tuple[object, ...]]:
    """Execute rendered model/test SQL over bounded raw inputs and optional staged damage."""
    assert not (singular and generic)
    assert rows
    changes = changes or {}
    assert set(changes) <= set(EXPECTED_COLUMNS)
    placeholders = ", ".join("(" + ", ".join("?" for _ in COLUMNS) + ")" for _ in rows)
    query = (
        render_sql(singular)
        if singular
        else render_generic(*generic)
        if generic
        else "select * from synthetic_staged"
    )
    fields = ", ".join(changes.get(column, column) + " as " + column for column in EXPECTED_COLUMNS)
    statement = (
        "with synthetic_order_payments ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), synthetic_orders (order_id) as (values (?)), projected as ("
        + render_sql("models/staging/stg_order_payments.sql")
        + "), synthetic_staged as (select "
        + fields
        + " from projected where "
        + staged_filter
        + staged_suffix
        + ") select * from ("
        + query
        + ") as test_result"
    )
    statement = statement.replace(" !~ ", " not regexp ").replace(" ~ ", " regexp ")
    statement = statement.replace("as numeric(18,2)", "as numeric")
    statement = sqlite_except_all(statement)
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
        connection.create_function("trunc", 1, lambda value: None if value is None else int(value))
        connection.create_function(
            "regexp",
            2,
            lambda pattern, value: (
                None
                if value is None
                else int(re.fullmatch(pattern.replace("[[:space:]]", r"\s"), value) is not None)
            ),
        )
        connection.execute("pragma query_only = on")
        result = connection.execute(
            statement, (*tuple(value for row in rows for value in row), parent)
        )
        if not singular and not generic:
            assert tuple(column[0] for column in result.description) == EXPECTED_COLUMNS
        return result.fetchall()
    finally:
        connection.close()


def test_split_components_keep_every_literal_source_field_lineage_and_row_without_parent_join() -> (
    None
):
    rows = [
        payment(),
        payment(_source_row=2, payment_sequential="2", payment_type="voucher"),
        payment(_source_row=3, payment_sequential="3", payment_value="0.10"),
    ]
    projected = run_sql(rows, parent=None)
    assert len(projected) == 3
    for source, staged in zip(rows, projected, strict=True):
        assert staged[:3] == source[:3]
        assert staged[3:6] == (int(source[3]), source[4], int(source[5]))
        assert Decimal(str(staged[6])) == Decimal(source[6])
        assert staged[7:] == (0, 0, 0)
    assert run_sql(rows, "tests/stg_order_payments_source_reconciliation.sql") == []


@pytest.mark.parametrize("method", METHODS)
def test_every_allowed_literal_method_is_retained_and_actual_dbt_method_test_passes(
    method: str,
) -> None:
    source = payment(payment_type=method)
    assert run_sql([source])[0][4] == method
    assert run_sql([source])[0][7:] == (0, 0, int(method == "not_defined"))
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == []
    assert run_sql([source], generic=("payment_type", "accepted_values")) == []


@pytest.mark.parametrize(
    "column,value,flags",
    [
        ("payment_installments", "0", (1, 0, 0)),
        ("payment_value", "0.00", (0, 1, 0)),
        ("payment_type", "not_defined", (0, 0, 1)),
    ],
)
def test_each_warning_preserves_source_zero_or_undefined_without_blocking(
    column: str,
    value: str,
    flags: tuple[int, ...],
) -> None:
    source = payment(**{column: value})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] == (value if column == "payment_type" else 0)
    assert projected[7:] == flags
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == []


def test_all_three_source_warnings_coexist_without_imputation() -> None:
    source = payment(payment_installments="0.0", payment_value="000.00", payment_type="not_defined")
    assert run_sql([source]) == [(LOAD, 1, ORDER, 1, "not_defined", 0, 0, 1, 1, 1)]
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == []


@pytest.mark.parametrize("column", COLUMNS[2:])
@pytest.mark.parametrize("missing", ["", None])
def test_each_missing_source_field_retains_row_blocks_and_does_not_invent_warning(
    column: str,
    missing: object,
) -> None:
    source = payment(**{column: missing})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    assert projected[7:] == (0, 0, 0)
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("column", COLUMNS)
def test_actual_dbt_not_null_blocks_each_missing_source_or_lineage(column: str) -> None:
    assert run_sql([payment(**{column: None})], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("flag", FLAGS)
def test_warning_flags_are_nonnull_and_actual_dbt_test_detects_null_mutation(flag: str) -> None:
    assert run_sql([payment()], generic=(flag, "not_null")) == []
    assert run_sql([payment()], generic=(flag, "not_null"), changes={flag: "null"}) == [(None,)]


@pytest.mark.parametrize(
    "column,text",
    [
        ("payment_sequential", "1.5"),
        ("payment_installments", "1.5"),
        ("payment_value", "1.234"),
        ("payment_value", "1e2"),
    ],
)
def test_rejected_numeric_input_becomes_null_with_false_flags_and_blocks(
    column: str, text: str
) -> None:
    source = payment(**{column: text})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    assert projected[7:] == (0, 0, 0)
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("column", ("payment_sequential", "payment_installments"))
def test_both_component_integer_fields_use_accepted_exact_integral_decimal_parser(
    column: str,
) -> None:
    source = payment(**{column: "1.2e1"})
    assert run_sql([source])[0][COLUMNS.index(column)] == 12
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == []


@pytest.mark.parametrize(
    "column,text,expected",
    [
        ("payment_sequential", "0", 0),
        ("payment_sequential", "-1", -1),
        ("payment_installments", "-1", -1),
    ],
)
def test_nonpositive_sequence_and_negative_installments_preserve_values_but_block(
    column: str,
    text: str,
    expected: int,
) -> None:
    source = payment(**{column: text})
    assert run_sql([source])[0][COLUMNS.index(column)] == expected
    assert run_sql([source])[0][7:] == (0, 0, 0)
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("method", ["Credit_card", " credit_card ", "unknown", "NOT_DEFINED"])
def test_invalid_literal_method_is_preserved_and_blocks_both_method_and_domain_tests(
    method: str,
) -> None:
    source = payment(payment_type=method)
    assert run_sql([source])[0][4] == method
    assert run_sql([source])[0][7:] == (0, 0, 0)
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=("payment_type", "accepted_values")) == [(method, 1)]


@pytest.mark.parametrize("order_id", ["A" * 32, "short", " " + ORDER])
def test_invalid_literal_order_key_is_preserved_and_blocks(order_id: str) -> None:
    source = payment(order_id=order_id)
    assert run_sql([source])[0][2] == order_id
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("ordinal", [None, 0, -1])
def test_missing_or_nonpositive_source_ordinal_blocks(ordinal: object) -> None:
    source = payment(_source_row=ordinal)
    assert run_sql([source])[0][1] == ordinal
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]


def test_actual_order_relationship_blocks_orphan_and_retains_component() -> None:
    source = payment(order_id="b" * 32)
    assert run_sql([source])[0][2] == "b" * 32
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == []
    assert run_sql([source], generic=("order_id", "relationships")) == [("b" * 32,)]
    assert run_sql([payment()], generic=("order_id", "relationships")) == []


def test_repeated_individual_keys_and_split_methods_satisfy_composite_grain() -> None:
    rows = [
        payment(),
        payment(_source_row=2, payment_sequential="2", payment_type="voucher"),
        payment(_source_row=3, order_id="b" * 32),
    ]
    assert len(run_sql(rows)) == 3
    assert run_sql(rows, "tests/stg_order_payments_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_payments_lineage_unique.sql") == []


def test_duplicate_component_key_at_distinct_lineage_is_retained_and_blocks_grain() -> None:
    rows = [payment(), payment(_source_row=2, payment_type="voucher", payment_value="0.00")]
    assert len(run_sql(rows)) == 2
    assert run_sql(rows, "tests/stg_order_payments_grain.sql") == [(1,)]
    assert run_sql(rows, "tests/stg_order_payments_lineage_unique.sql") == []


def test_duplicate_lineage_at_distinct_component_key_blocks_lineage_only() -> None:
    rows = [payment(), payment(payment_sequential="2")]
    assert run_sql(rows, "tests/stg_order_payments_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_payments_lineage_unique.sql") == [(1,)]


def test_source_ordinal_can_repeat_in_distinct_loads() -> None:
    rows = [payment(), payment(_load_id="22222222-2222-4222-8222-222222222222", order_id="b" * 32)]
    assert run_sql(rows, "tests/stg_order_payments_lineage_unique.sql") == []


@pytest.mark.parametrize(
    "column,expression",
    [
        ("_load_id", "'22222222-2222-4222-8222-222222222222'"),
        ("_source_row", "_source_row+1"),
        ("order_id", "'" + "b" * 32 + "'"),
        ("payment_sequential", "payment_sequential+1"),
        ("payment_type", "'boleto'"),
        ("payment_installments", "payment_installments+1"),
        ("payment_value", "payment_value+0.01"),
        ("is_zero_installments", "true"),
        ("is_zero_payment_value", "true"),
        ("is_undefined_payment_type", "true"),
    ],
)
def test_multiset_reconciliation_detects_each_source_lineage_or_flag_substitution(
    column: str,
    expression: str,
) -> None:
    assert run_sql(
        [payment()],
        "tests/stg_order_payments_source_reconciliation.sql",
        changes={column: expression},
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_dropped_or_extra_duplicate_component() -> None:
    rows = [payment(), payment(_source_row=2, payment_sequential="2")]
    assert run_sql(
        rows, "tests/stg_order_payments_source_reconciliation.sql", staged_filter="_source_row<>1"
    ) == [("missing_from_staging", 1)]
    assert run_sql(
        rows,
        "tests/stg_order_payments_source_reconciliation.sql",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_same_count_duplicate_substitution() -> None:
    rows = [payment(), payment(_source_row=2, payment_sequential="2")]
    assert run_sql(
        rows,
        "tests/stg_order_payments_source_reconciliation.sql",
        staged_filter="_source_row=1",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_rejected_values_and_warning_flags_reconcile_while_domains_still_block() -> None:
    source = payment(payment_installments="1.5", payment_value="1.234", payment_type="not_defined")
    assert run_sql([source])[0][7:] == (0, 0, 1)
    assert run_sql([source], "tests/stg_order_payments_source_reconciliation.sql") == []
    assert run_sql([source], "tests/stg_order_payments_source_domains.sql") == [(1,)]


def test_contract_declares_exact_types_methods_flags_and_sixteen_data_tests() -> None:
    contract = model_contract()
    assert contract["config"] == {"materialized": "view", "schema": "staging"}
    columns = contract["columns"]
    assert tuple(record["name"] for record in columns) == EXPECTED_COLUMNS
    assert tuple(record["data_type"] for record in columns) == (
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
    assert sum(len(record["data_tests"]) for record in columns) + 4 == 16
    assert all("not_null" in record["data_tests"] for record in columns)
    method = next(record for record in columns if record["name"] == "payment_type")
    assert method["data_tests"][1]["accepted_values"]["arguments"]["values"] == list(METHODS)
