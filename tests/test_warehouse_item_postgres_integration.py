"""Native item SQL checks using bounded synthetic, read-only VALUES inputs.

Render the actual item model/macros, singular domain/grain/lineage queries, and
dbt's generic null/reference tests. No raw records, fixture tables, temporary
relations, or warehouse writes are used. Expected amounts use independent
Decimal literals; expected timestamps are naive whole-second datetime literals.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_ITEM_INTEGRATION") != "1",
    reason="Native read-only item SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
OTHER_LOAD = UUID("22222222-2222-4222-8222-222222222222")
ORDER_ID = "a" * 32
PRODUCT_ID = "b" * 32
SELLER_ID = "c" * 32
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["order_items"].columns)
MONEY_COLUMNS = ("price", "freight_value")
REFERENCES = {
    "order_id": ("stg_orders", ORDER_ID),
    "product_id": ("stg_products", PRODUCT_ID),
    "seller_id": ("stg_sellers", SELLER_ID),
}

# Money expectations deliberately do not call parse_money or a production macro.
MONEY_CASES = (
    ("zero", "0", Decimal("0.00")),
    ("one-decimal", "0.1", Decimal("0.10")),
    ("two-decimals", "123.45", Decimal("123.45")),
    ("leading-zeroes", "00012.30", Decimal("12.30")),
    ("maximum-numeric18-2", "9999999999999999.99", Decimal("9999999999999999.99")),
    ("above-maximum", "10000000000000000.00", None),
    ("rounding-would-hide-extra-scale", "1.005", None),
    ("extra-zero-scale-is-still-invalid", "1.000", None),
    ("negative", "-0.01", None),
    ("signed-zero", "-0.00", None),
    ("explicit-plus", "+1.00", None),
    ("exponent", "1e2", None),
    ("no-integer-digits", ".50", None),
    ("no-fraction-digits", "1.", None),
    ("leading-space", " 1.00", None),
    ("trailing-newline", "1.00\n", None),
    ("whitespace-only", " \t", None),
    ("non-ascii-digits", "１２.３４", None),
    ("malformed", "bad-money", None),
    ("nan", "NaN", None),
    ("infinity", "Infinity", None),
    # Accepted by the decimal grammar but beyond PostgreSQL unconstrained numeric.
    # The bounded 128 KiB value exercises pg_input_is_valid before any cast.
    ("postgres-numeric-input-overflow", "9" * 131073, None),
)
SEQUENCE_CASES = (
    ("positive", "1", 1, 0),
    ("exact-beyond-binary64", "9007199254740993.0", 9007199254740993, 0),
    ("signed64-maximum", "9223372036854775807.0", 9223372036854775807, 0),
    ("integral-decimal-exponent", " \t+2e1\n", 20, 0),
    ("zero-domain-failure", "0", 0, 1),
    ("negative-preserved-domain-failure", "-1", -1, 1),
    ("signed64-minimum-domain-failure", "-9223372036854775808", -9223372036854775808, 1),
    ("above-signed64", "9223372036854775808", None, 1),
    ("below-signed64", "-9223372036854775809", None, 1),
    ("fraction-beyond-binary64", "1.000000000000000000000000001", None, 1),
    ("numeric-input-overflow", "1e99999999999999999999999", None, 1),
    ("nonfinite", "NaN", None, 1),
)
TIMESTAMP_CASES = (
    ("ordinary-naive", "2018-01-02 03:04:05", datetime(2018, 1, 2, 3, 4, 5)),
    ("valid-leap-day", "2000-02-29 23:59:59", datetime(2000, 2, 29, 23, 59, 59)),
    ("ns-lower-second", "1677-09-21 00:12:44", datetime(1677, 9, 21, 0, 12, 44)),
    ("ns-upper-second", "2262-04-11 23:47:16", datetime(2262, 4, 11, 23, 47, 16)),
    ("invalid-calendar", "2018-02-29 03:04:05", None),
    ("hour24-normalization", "2018-01-02 24:00:00", None),
    ("timezone-conversion-risk", "2018-01-02 03:04:05-03:00", None),
    ("fractional-second", "2018-01-02 03:04:05.000", None),
    ("dynamic-now", "now", None),
    ("below-ns-second", "1677-09-21 00:12:43", None),
    ("above-ns-second", "2262-04-11 23:47:17", None),
)


def _source_row(changes: dict[str, object] | None = None) -> tuple[object, ...]:
    fields: dict[str, object] = {
        "_load_id": LOAD,
        "_source_row": 1,
        "order_id": ORDER_ID,
        "order_item_id": "1",
        "product_id": PRODUCT_ID,
        "seller_id": SELLER_ID,
        "shipping_limit_date": "2018-01-02 03:04:05",
        "price": "0.10",
        "freight_value": "0.20",
    }
    fields.update(changes or {})
    return tuple(fields[column] for column in SOURCE_COLUMNS)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_sql(relative_path: str) -> str:
    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_items")
        return "synthetic_items"

    def ref(model: str) -> str:
        assert model in {"stg_order_items", *(model for model, _ in REFERENCES.values())}
        return "synthetic_projection" if model == "stg_order_items" else "synthetic_" + model

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = "\n".join(
        (PROJECT / "macros" / filename).read_text("utf-8")
        for filename in ("source_numeric.sql", "source_timestamp.sql", "source_money.sql")
    )
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        _environment()
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_test_sql(name: str, **arguments: str) -> str:
    # Execute the installed dbt generic-test SQL, substituting only fixture names.
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
    # MATERIALIZED retains raw-table-like column inputs; the inline mode probes
    # custom-plan folding of otherwise unreachable casts. NULL remains typed text.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in SOURCE_COLUMNS[2:]))
    value_row = "(" + ", ".join(placeholders) + ")"
    materialization = "materialized " if materialized else ""
    ctes = [
        "synthetic_items ("
        + ", ".join(SOURCE_COLUMNS)
        + ") as "
        + materialization
        + "(values "
        + ", ".join(value_row for _ in rows)
        + ")"
    ]
    parameters = [value for row in rows for value in row]
    for column, (model, identifier) in REFERENCES.items():
        parent_rows = 2 if duplicate_parents else 1
        ctes.append(
            "synthetic_"
            + model
            + " ("
            + column
            + ") as materialized (values "
            + ", ".join("(%s::text)" for _ in range(parent_rows))
            + ")"
        )
        parameters.extend([identifier] * parent_rows)
    ctes.append(
        "synthetic_projection as (" + _render_sql("models/staging/stg_order_items.sql") + ")"
    )
    return "with " + ", ".join(ctes) + " ", tuple(parameters)


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
    """Roll back a failing case's savepoint without poisoning subsequent cases."""
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
        cte + "select * from synthetic_projection order by _source_row, order_id, order_item_id",
        parameters,
    )
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == SOURCE_COLUMNS
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
        connection, (row,), "stg_order_items_source_domains.sql", "invalid_source_value_rows"
    )


def _generic_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    name: str,
    **arguments: str,
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


def _assert_identity(projected: dict[str, object]) -> None:
    assert projected["_load_id"] == LOAD
    assert projected["_source_row"] == 1
    assert projected["order_id"] == ORDER_ID
    assert projected["product_id"] == PRODUCT_ID
    assert projected["seller_id"] == SELLER_ID


@pytest.mark.parametrize(
    "source_value,expected",
    [(value, expected) for _, value, expected in MONEY_CASES],
    ids=[name for name, _, _ in MONEY_CASES],
)
def test_exact_money_grammar_range_scale_and_actual_source_domains(
    transformer_connection: psycopg.Connection, source_value: str, expected: Decimal | None
) -> None:
    row = _source_row(dict.fromkeys(MONEY_COLUMNS, source_value))
    projected = _single_projection(transformer_connection, row)
    _assert_identity(projected)
    assert projected["order_item_id"] == 1
    assert projected["shipping_limit_date"] == datetime(2018, 1, 2, 3, 4, 5)
    for column in MONEY_COLUMNS:
        assert projected[column] == expected
        if expected is not None:
            assert type(projected[column]) is Decimal
            assert projected[column].as_tuple().exponent == -2
    # Two invalid amount fields in one source row count as one invalid row.
    assert _domain_failures(transformer_connection, row) == (expected is None)


@pytest.mark.parametrize(
    "source_value,expected,failure_count",
    [(value, expected, failures) for _, value, expected, failures in SEQUENCE_CASES],
    ids=[name for name, _, _, _ in SEQUENCE_CASES],
)
def test_sequence_is_exact_signed64_with_a_separate_positive_domain(
    transformer_connection: psycopg.Connection,
    source_value: str,
    expected: int | None,
    failure_count: int,
) -> None:
    row = _source_row({"order_item_id": source_value})
    projected = _single_projection(transformer_connection, row)
    _assert_identity(projected)
    assert projected["order_item_id"] == expected
    assert expected is None or type(projected["order_item_id"]) is int
    assert projected["price"] == Decimal("0.10")
    assert _domain_failures(transformer_connection, row) == failure_count


@pytest.mark.parametrize(
    "source_value,expected",
    [(value, expected) for _, value, expected in TIMESTAMP_CASES],
    ids=[name for name, _, _ in TIMESTAMP_CASES],
)
def test_shipping_deadline_uses_strict_source_timestamp_and_naive_boundaries(
    transformer_connection: psycopg.Connection, source_value: str, expected: datetime | None
) -> None:
    row = _source_row({"shipping_limit_date": source_value})
    projected = _single_projection(transformer_connection, row)
    _assert_identity(projected)
    assert projected["shipping_limit_date"] == expected
    if expected is not None:
        assert type(projected["shipping_limit_date"]) is datetime
        assert projected["shipping_limit_date"].tzinfo is None
        assert projected["shipping_limit_date"].microsecond == 0
    assert _domain_failures(transformer_connection, row) == (expected is None)


@pytest.mark.parametrize("column", tuple(TABLES["order_items"].columns))
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_each_mandatory_source_field_absence_is_retained_and_blocked(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), "not_null", column_name=column) == 1


@pytest.mark.parametrize("column", MONEY_COLUMNS)
def test_each_money_field_independently_rejects_excess_scale(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: "1.000"})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    other = "freight_value" if column == "price" else "price"
    assert projected[other] == Decimal("0.20" if other == "freight_value" else "0.10")
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", tuple(REFERENCES))
@pytest.mark.parametrize("source_value", ["D" * 32, "short-id"], ids=["uppercase", "malformed"])
def test_id_spelling_is_retained_and_invalid_domains_block_acceptance(
    transformer_connection: psycopg.Connection, column: str, source_value: str
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] == source_value
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("source_value", [0, -1, None], ids=["zero", "negative", "null"])
def test_invalid_source_ordinals_are_preserved_and_blocked(
    transformer_connection: psycopg.Connection, source_value: int | None
) -> None:
    row = _source_row({"_source_row": source_value})
    assert _single_projection(transformer_connection, row)["_source_row"] == source_value
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", ("_load_id", "_source_row"))
def test_missing_lineage_fails_the_actual_dbt_null_test(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: None})
    assert _single_projection(transformer_connection, row)[column] is None
    assert _generic_failures(transformer_connection, (row,), "not_null", column_name=column) == 1


@pytest.mark.parametrize("column", tuple(REFERENCES))
def test_each_missing_parent_reference_blocks_without_dropping_the_item(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: "d" * 32})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] == "d" * 32
    assert _domain_failures(transformer_connection, row) == 0
    model, _ = REFERENCES[column]
    assert (
        _generic_failures(
            transformer_connection,
            (row,),
            "relationships",
            column_name=column,
            to="synthetic_" + model,
            field=column,
        )
        == 1
    )


def test_positive_shared_sequences_and_repeated_parents_keep_the_item_grain(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row(),
        _source_row({"_source_row": 2, "order_item_id": "2"}),
        _source_row({"_source_row": 3, "order_id": "d" * 32}),
    )
    projected = _projection(transformer_connection, rows, duplicate_parents=True)
    assert [(row["order_id"], row["order_item_id"]) for row in projected] == [
        (ORDER_ID, 1),
        (ORDER_ID, 2),
        ("d" * 32, 1),
    ]
    assert all(
        row["product_id"] == PRODUCT_ID and row["seller_id"] == SELLER_ID for row in projected
    )
    assert (
        _singular_failures(
            transformer_connection, rows, "stg_order_items_grain.sql", "duplicate_item_key_groups"
        )
        == 0
    )
    for column, (model, _) in REFERENCES.items():
        assert (
            _generic_failures(
                transformer_connection,
                (_source_row(),),
                "relationships",
                column_name=column,
                to="synthetic_" + model,
                field=column,
            )
            == 0
        )


def test_duplicate_item_keys_are_retained_but_fail_actual_composite_grain(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (_source_row(), _source_row({"_source_row": 2}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection, rows, "stg_order_items_grain.sql", "duplicate_item_key_groups"
        )
        == 1
    )
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_items_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == 0
    )


@pytest.mark.parametrize("second_load,expected", [(LOAD, 1), (OTHER_LOAD, 0)])
def test_lineage_uniqueness_is_per_load_and_independent_of_item_sequence(
    transformer_connection: psycopg.Connection, second_load: UUID, expected: int
) -> None:
    rows = (_source_row(), _source_row({"_load_id": second_load, "order_item_id": "2"}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_items_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == expected
    )


def test_money_sums_remain_exact_and_do_not_cross_reconcile_price_and_freight(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row({"price": "0.1", "freight_value": "1.23"}),
        _source_row(
            {"_source_row": 2, "order_item_id": "2", "price": "0.2", "freight_value": "4.56"}
        ),
    )
    cte, parameters = _synthetic_cte(rows)
    result = transformer_connection.execute(
        cte
        + "select count(*), sum(price), sum(freight_value), "
        + "bool_and(pg_typeof(price)::text = 'numeric'), "
        + "bool_and(pg_typeof(shipping_limit_date)::text = 'timestamp without time zone') "
        + "from synthetic_projection",
        parameters,
    ).fetchone()
    assert result == (2, Decimal("0.30"), Decimal("5.79"), True, True)
    assert type(result[1]) is Decimal
    assert type(result[2]) is Decimal


@pytest.mark.parametrize(
    "changes",
    [
        {"price": "1.000", "freight_value": "10000000000000000.00"},
        {"price": "9" * 131073, "order_item_id": "1e99999999999999999999999"},
        {"shipping_limit_date": "2018-02-30 03:04:05"},
    ],
    ids=["money-scale-and-typmod-overflow", "numeric-input-overflow", "invalid-calendar"],
)
def test_inline_constants_are_guarded_before_immutable_casts(
    transformer_connection: psycopg.Connection, changes: dict[str, str]
) -> None:
    projected = _single_projection(transformer_connection, _source_row(changes), materialized=False)
    for column in changes:
        assert projected[column] is None
