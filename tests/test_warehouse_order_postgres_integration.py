"""Native order SQL checks using bounded synthetic, read-only VALUES inputs.

Render the actual staging macro/model, singular source-domain query, and dbt's
generic null/reference tests. No raw records, fixture tables, temporary relations,
or warehouse writes are used. Expected dates and flags are independent literals.
The strict warehouse timestamp grammar rejects Phase 2 parser normalization of
nonpadded dates, leap seconds, and dynamic ``now``/``today`` values.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.validation.contracts import TABLES
from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_ORDER_INTEGRATION") != "1",
    reason="Native read-only order SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
ORDER_ID = "a" * 32
CUSTOMER_ID = "b" * 32
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["orders"].columns)
CUSTOMER_COLUMNS = ("_load_id", "_source_row", *TABLES["customers"].columns)
TIMESTAMP_COLUMNS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
OPTIONAL_EVENTS = (
    ("order_approved_at", "is_missing_approval", "is_delivered_missing_approval"),
    (
        "order_delivered_carrier_date",
        "is_missing_carrier_delivery",
        "is_delivered_missing_carrier_delivery",
    ),
    (
        "order_delivered_customer_date",
        "is_missing_customer_delivery",
        "is_delivered_missing_customer_delivery",
    ),
)
MISSING_FLAGS = tuple(missing for _, missing, _ in OPTIONAL_EVENTS)
DELIVERED_MISSING_FLAGS = tuple(delivered for _, _, delivered in OPTIONAL_EVENTS)
REVERSAL_CASES = (
    (
        "order_purchase_timestamp",
        "order_approved_at",
        "is_approval_before_purchase",
    ),
    (
        "order_purchase_timestamp",
        "order_delivered_carrier_date",
        "is_carrier_delivery_before_purchase",
    ),
    (
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "is_customer_delivery_before_purchase",
    ),
    (
        "order_approved_at",
        "order_delivered_carrier_date",
        "is_carrier_delivery_before_approval",
    ),
    (
        "order_approved_at",
        "order_delivered_customer_date",
        "is_customer_delivery_before_approval",
    ),
    (
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "is_customer_delivery_before_carrier_delivery",
    ),
)
REVERSAL_FLAGS = tuple(flag for _, _, flag in REVERSAL_CASES)
FLAGS = (*MISSING_FLAGS, *DELIVERED_MISSING_FLAGS, *REVERSAL_FLAGS)
EXPECTED_COLUMNS = (*SOURCE_COLUMNS, *FLAGS)

# No expected timestamp calls a production macro or the Phase 2 pandas parser.
VALID_TIMESTAMPS = (
    ("source-hms", "2018-01-02 03:04:05", datetime(2018, 1, 2, 3, 4, 5)),
    ("leap-day", "2000-02-29 23:59:59", datetime(2000, 2, 29, 23, 59, 59)),
    ("ns-lower-second", "1677-09-21 00:12:44", datetime(1677, 9, 21, 0, 12, 44)),
    ("ns-upper-second", "2262-04-11 23:47:16", datetime(2262, 4, 11, 23, 47, 16)),
)
INVALID_TIMESTAMPS = (
    ("malformed", "not-a-date"),
    ("nonleap-february", "2018-02-29 10:00:00"),
    ("century-is-not-leap", "1900-02-29 10:00:00"),
    ("calendar-day-overflow", "2018-04-31 10:00:00"),
    ("zero-day", "2018-01-00 10:00:00"),
    ("zero-month", "2018-00-01 10:00:00"),
    ("month-overflow", "2018-13-01 10:00:00"),
    ("hour24-no-normalization", "2018-01-01 24:00:00"),
    ("minute60", "2018-01-01 10:60:00"),
    ("leap-second-no-normalization", "2018-01-01 23:59:60"),
    ("nonpadded-no-normalization", "2018-1-1 1:2:3"),
    ("fractional-seconds", "2018-01-01 10:00:00.123"),
    ("zero-fraction-still-not-source-hms", "2018-01-01 10:00:00.000000"),
    ("utc-offset", "2018-01-01 10:00:00+00:00"),
    ("offset-with-conversion-risk", "2018-01-01 10:00:00-03:00"),
    ("z-timezone", "2018-01-01 10:00:00Z"),
    ("named-timezone", "2018-01-01 10:00:00 UTC"),
    ("iso-t-separator", "2018-01-01T10:00:00"),
    ("date-only", "2018-01-01"),
    ("leading-space", " 2018-01-01 10:00:00"),
    ("trailing-space", "2018-01-01 10:00:00 "),
    ("trailing-newline", "2018-01-01 10:00:00\n"),
    ("nonempty-whitespace", " \t\n"),
    ("non-ascii-digits", "２０１８-01-01 10:00:00"),
    ("below-ns-second", "1677-09-21 00:12:43"),
    ("above-ns-second", "2262-04-11 23:47:17"),
    ("year-outside-phase2-range", "2300-01-01 00:00:00"),
    ("zero-year", "0000-01-01 00:00:00"),
    ("bc-calendar-extension", "2018-01-01 10:00:00 BC"),
    ("infinity", "infinity"),
    ("negative-infinity", "-infinity"),
    ("dynamic-now", "now"),
    ("dynamic-today", "today"),
    ("epoch-alias", "epoch"),
    ("nat-token", "NaT"),
)


def _source_row(changes: dict[str, object] | None = None) -> tuple[object, ...]:
    fields: dict[str, object] = dict.fromkeys(TIMESTAMP_COLUMNS, "2018-01-02 03:04:05")
    fields.update(
        _load_id=LOAD,
        _source_row=1,
        order_id=ORDER_ID,
        customer_id=CUSTOMER_ID,
        order_status="delivered",
    )
    fields.update(changes or {})
    return tuple(fields[column] for column in SOURCE_COLUMNS)


def _customer_row() -> tuple[object, ...]:
    return (LOAD, 1, CUSTOMER_ID, "c" * 32, "00123", "São Paulo", "SP")


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_sql(relative_path: str) -> str:
    def source(schema: str, table: str) -> str:
        assert schema == "raw"
        assert table in {"orders", "customers"}
        return "synthetic_" + table

    def ref(model: str) -> str:
        assert model in {"stg_orders", "stg_customers"}
        return {
            "stg_orders": "synthetic_projection",
            "stg_customers": "synthetic_customer_projection",
        }[model]

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = (PROJECT / "macros/source_timestamp.sql").read_text("utf-8")
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        _environment()
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_test_sql(name: str, **arguments: str) -> str:
    # Execute dbt's actual generic-test SQL, with only fixture relation names
    # substituted. Aggregate the result before it leaves PostgreSQL.
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    template = _environment().from_string(macro)
    module = template.make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", **arguments
    ).strip()


def _values_cte(name: str, columns: tuple[str, ...], *, materialized: bool) -> str:
    # MATERIALIZED keeps bound inputs as raw-table column values. Explicit
    # types ensure a synthetic NULL does not change the raw text contract.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in columns[2:]))
    materialization = "materialized " if materialized else ""
    return (
        name
        + " ("
        + ", ".join(columns)
        + ") as "
        + materialization
        + "(values ("
        + ", ".join(placeholders)
        + "))"
    )


def _synthetic_cte(*, materialized: bool = True, staged_orders: bool = False) -> str:
    ctes = [
        _values_cte("synthetic_orders", SOURCE_COLUMNS, materialized=materialized),
        _values_cte("synthetic_customers", CUSTOMER_COLUMNS, materialized=materialized),
        "synthetic_customer_projection as ("
        + _render_sql("models/staging/stg_customers.sql")
        + ")",
    ]
    if staged_orders:
        ctes.append(
            "synthetic_projection as (" + _render_sql("models/staging/stg_orders.sql") + ")"
        )
    return "with " + ", ".join(ctes) + " "


@pytest.fixture(scope="module")
def transformer_connection() -> Iterator[psycopg.Connection]:
    # Existing config enforces purpose-specific credentials and verify-full TLS.
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
    """A SQL failure rolls back its savepoint without poisoning later cases."""
    with transformer_connection.transaction():
        yield


def _projection(
    connection: psycopg.Connection, row: tuple[object, ...], *, materialized: bool = True
) -> dict[str, object]:
    statement = (
        _synthetic_cte(materialized=materialized)
        + "select * from ("
        + _render_sql("models/staging/stg_orders.sql")
        + ") as projected"
    )
    result = connection.execute(statement, (*row, *_customer_row()))
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == EXPECTED_COLUMNS
    records = result.fetchall()
    assert len(records) == 1
    return dict(zip(names, records[0], strict=True))


def _domain_failures(connection: psycopg.Connection, row: tuple[object, ...]) -> int:
    statement = (
        _synthetic_cte(staged_orders=True)
        + "select * from ("
        + _render_sql("tests/stg_orders_source_domains.sql")
        + ") as source_domain_result"
    )
    result = connection.execute(statement, (*row, *_customer_row()))
    assert result.description is not None
    assert tuple(column.name for column in result.description) == ("invalid_source_value_rows",)
    records = result.fetchall()
    if not records:
        return 0
    assert len(records) == 1
    return records[0][0]


def _generic_failures(
    connection: psycopg.Connection, row: tuple[object, ...], name: str, **arguments: str
) -> int:
    statement = (
        _synthetic_cte(staged_orders=True)
        + "select count(*) from ("
        + _generic_test_sql(name, **arguments)
        + ") as generic_result"
    )
    record = connection.execute(statement, (*row, *_customer_row())).fetchone()
    assert record is not None
    return record[0]


def _assert_flags(projected: dict[str, object], true_flags: tuple[str, ...] = ()) -> None:
    assert all(type(projected[flag]) is bool for flag in FLAGS)
    assert {flag for flag in FLAGS if projected[flag]} == set(true_flags)


def _assert_lineage_and_keys(projected: dict[str, object]) -> None:
    assert projected["_load_id"] == LOAD
    assert projected["_source_row"] == 1
    assert projected["order_id"] == ORDER_ID
    assert projected["customer_id"] == CUSTOMER_ID


@pytest.mark.parametrize(
    ("source_value", "expected"),
    [(value, expected) for _, value, expected in VALID_TIMESTAMPS],
    ids=[name for name, _, _ in VALID_TIMESTAMPS],
)
def test_native_source_hms_is_exact_naive_and_phase2_second_bounds_are_retained(
    transformer_connection: psycopg.Connection, source_value: str, expected: datetime
) -> None:
    row = _source_row(dict.fromkeys(TIMESTAMP_COLUMNS, source_value))
    projected = _projection(transformer_connection, row)
    _assert_lineage_and_keys(projected)
    assert projected["order_status"] == "delivered"
    for column in TIMESTAMP_COLUMNS:
        assert projected[column] == expected
        assert type(projected[column]) is datetime
        assert projected[column].tzinfo is None
        assert projected[column].microsecond == 0
    _assert_flags(projected)
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize(
    "source_value",
    [value for _, value in INVALID_TIMESTAMPS],
    ids=[name for name, _ in INVALID_TIMESTAMPS],
)
def test_native_rejected_timestamp_forms_are_null_and_one_aggregate_failure(
    transformer_connection: psycopg.Connection, source_value: str
) -> None:
    row = _source_row(dict.fromkeys(TIMESTAMP_COLUMNS, source_value))
    projected = _projection(transformer_connection, row)
    _assert_lineage_and_keys(projected)
    assert all(projected[column] is None for column in TIMESTAMP_COLUMNS)
    # Failed parsing is typed absence, while source missingness stays false.
    _assert_flags(projected, DELIVERED_MISSING_FLAGS)
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", TIMESTAMP_COLUMNS)
def test_each_timestamp_column_independently_blocks_invalid_nonempty_input(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: "2018-02-30 03:04:05"})
    projected = _projection(transformer_connection, row)
    assert projected[column] is None
    for other in set(TIMESTAMP_COLUMNS) - {column}:
        assert projected[other] == datetime(2018, 1, 2, 3, 4, 5)
    delivered_flags = tuple(flag for event, _, flag in OPTIONAL_EVENTS if event == column)
    _assert_flags(projected, delivered_flags)
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
@pytest.mark.parametrize("column,missing_flag,delivered_flag", OPTIONAL_EVENTS)
def test_optional_missing_source_remains_valid_and_distinct_from_parse_failure(
    transformer_connection: psycopg.Connection,
    column: str,
    missing_flag: str,
    delivered_flag: str,
    source_value: str | None,
) -> None:
    row = _source_row({column: source_value, "order_status": "shipped"})
    projected = _projection(transformer_connection, row)
    _assert_lineage_and_keys(projected)
    assert projected[column] is None
    assert projected["order_status"] == "shipped"
    _assert_flags(projected, (missing_flag,))
    assert projected[delivered_flag] is False
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize("column,missing_flag,delivered_flag", OPTIONAL_EVENTS)
def test_each_delivered_missing_event_is_retained_as_a_warning(
    transformer_connection: psycopg.Connection,
    column: str,
    missing_flag: str,
    delivered_flag: str,
) -> None:
    row = _source_row({column: ""})
    projected = _projection(transformer_connection, row)
    _assert_lineage_and_keys(projected)
    assert projected["order_status"] == "delivered"
    assert projected[column] is None
    _assert_flags(projected, (missing_flag, delivered_flag))
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize("column", ("order_purchase_timestamp", "order_estimated_delivery_date"))
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_mandatory_source_date_absence_is_a_blocking_error(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flags(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, row, "not_null", column_name=column) == 1


@pytest.mark.parametrize("earlier,later,reversal_flag", REVERSAL_CASES)
def test_each_lifecycle_reversal_retains_exact_events_and_named_warning(
    transformer_connection: psycopg.Connection, earlier: str, later: str, reversal_flag: str
) -> None:
    # Keep only the tested optional pair, plus mandatory purchase/estimate.
    # For a pair between optional events, purchase remains earlier than both.
    changes = {event: "" for event, _, _ in OPTIONAL_EVENTS}
    changes.update(
        order_purchase_timestamp="2018-01-01 00:00:00",
        order_estimated_delivery_date="2018-01-04 00:00:00",
        order_status="shipped",
    )
    changes[earlier] = "2018-01-03 00:00:00"
    changes[later] = "2018-01-02 00:00:00"
    row = _source_row(changes)
    projected = _projection(transformer_connection, row)
    _assert_lineage_and_keys(projected)
    assert projected[earlier] == datetime(2018, 1, 3)
    assert projected[later] == datetime(2018, 1, 2)
    assert projected["order_estimated_delivery_date"] == datetime(2018, 1, 4)
    missing_flags = tuple(
        flag for event, flag, _ in OPTIONAL_EVENTS if event not in {earlier, later}
    )
    _assert_flags(projected, (*missing_flags, reversal_flag))
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize("column", ("order_id", "customer_id", "order_status"))
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_mandatory_keys_and_status_absence_fail_without_discarding_the_row(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _projection(transformer_connection, row)
    assert projected[column] is None
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, row, "not_null", column_name=column) == 1


@pytest.mark.parametrize(
    "column,source_value",
    [
        ("order_id", "A" * 32),
        ("order_id", "short-id"),
        ("customer_id", "B" * 32),
        ("customer_id", "short-id"),
        ("order_status", "Delivered"),
        ("order_status", " delivered "),
        ("order_status", "unrecognized"),
        ("_source_row", 0),
        ("_source_row", -1),
        ("_source_row", None),
    ],
)
def test_required_source_domains_reject_invalid_literals_and_ordinals(
    transformer_connection: psycopg.Connection, column: str, source_value: object
) -> None:
    row = _source_row({column: source_value})
    projected = _projection(transformer_connection, row)
    assert projected[column] == source_value
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("column", ("_load_id", "_source_row"))
def test_missing_lineage_is_blocked_by_the_actual_dbt_null_test(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: None})
    projected = _projection(transformer_connection, row)
    assert projected[column] is None
    assert _generic_failures(transformer_connection, row, "not_null", column_name=column) == 1


@pytest.mark.parametrize(
    ("customer_id", "expected_failures"),
    [(CUSTOMER_ID, 0), ("d" * 32, 1)],
    ids=["valid-source-customer", "mandatory-missing-reference"],
)
def test_actual_dbt_customer_reference_uses_staged_synthetic_customers(
    transformer_connection: psycopg.Connection, customer_id: str, expected_failures: int
) -> None:
    row = _source_row({"customer_id": customer_id})
    projected = _projection(transformer_connection, row)
    assert projected["customer_id"] == customer_id
    assert _domain_failures(transformer_connection, row) == 0
    assert (
        _generic_failures(
            transformer_connection,
            row,
            "relationships",
            column_name="customer_id",
            to="synthetic_customer_projection",
            field="customer_id",
        )
        == expected_failures
    )


@pytest.mark.parametrize(
    "source_value",
    ["2018-02-30 03:04:05", "2018-01-01 24:00:00", "now", "infinity"],
    ids=["invalid-calendar", "hour24", "dynamic-now", "infinity"],
)
def test_inline_constants_are_guarded_before_timestamp_casts(
    transformer_connection: psycopg.Connection, source_value: str
) -> None:
    # Regression for custom-plan folding of an invalid value in a CASE arm.
    row = _source_row(dict.fromkeys(TIMESTAMP_COLUMNS, source_value))
    projected = _projection(transformer_connection, row, materialized=False)
    assert all(projected[column] is None for column in TIMESTAMP_COLUMNS)
    _assert_flags(projected, DELIVERED_MISSING_FLAGS)
