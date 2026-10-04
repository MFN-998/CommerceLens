"""Opt-in native fact-order checks with bounded read-only typed CTEs.

Render the adopted model, singular checks and installed YAML-configured dbt
generic macros. Python supplies the independent literal join/date oracle.
Fixtures contain only synthetic values; no warehouse objects or records change.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack, suppress
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_ORDERS_INTEGRATION") != "1",
    reason="Native read-only fact-order SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
FLAGS = (
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
)
CLOCKS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "order_id",
    "customer_id",
    "order_status",
    *CLOCKS,
    *FLAGS,
)
CUSTOMER_COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
MAPPED_COLUMNS = (
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
    "customer_load_id",
    "customer_source_row",
)
DATE_COLUMNS = (
    "purchase_calendar_date",
    "approval_calendar_date",
    "carrier_delivery_calendar_date",
    "customer_delivery_calendar_date",
    "estimated_delivery_calendar_date",
)
COLUMNS = (*SOURCE_COLUMNS, *MAPPED_COLUMNS, *DATE_COLUMNS)
SOURCE_TYPES = (
    "uuid",
    "bigint",
    *("text",) * 3,
    *("timestamp without time zone",) * 5,
    *("boolean",) * 12,
)
CUSTOMER_TYPES = ("uuid", "bigint", *("text",) * 5)
TYPES = (*SOURCE_TYPES, *("text",) * 4, "uuid", "bigint", *("date",) * 5)
TYPE_CODES = (2950, 20, *(25,) * 3, *(1114,) * 5, *(16,) * 12, *(25,) * 4, 2950, 20, *(1082,) * 5)
REQUIRED = tuple(c for c in COLUMNS if c not in (*CLOCKS[1:4], *DATE_COLUMNS[1:4]))
STATUSES = tuple(
    "created approved invoiced processing shipped delivered unavailable canceled".split()
)
STATES = tuple(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)
SINGULARS = (
    "fact_orders_domains",
    "fact_orders_source_reconciliation",
    "fact_orders_relationships",
)
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
LOAD_C = UUID("33333333-3333-4333-8333-333333333333")
TARGET_ID = "0" + "a" * 31
CUSTOMER_IDS = tuple(character * 32 for character in "abcde")
IDENTITIES = ("1" * 32, "2" * 32, "3" * 32)
CUSTOMERS = (
    (LOAD_B, 4294967297, CUSTOMER_IDS[0], IDENTITIES[0], "00123", " São Paulo ", "SP"),
    (LOAD_A, 1, CUSTOMER_IDS[1], IDENTITIES[0], "123", "新しい🙂", "RJ"),
    (LOAD_C, 1, CUSTOMER_IDS[2], IDENTITIES[0], "0", "Café d'Água", "PB"),
    (LOAD_B, 2, CUSTOMER_IDS[3], IDENTITIES[1], "888", "são paulo", "SP"),
    (LOAD_C, 2, CUSTOMER_IDS[4], IDENTITIES[2], "888", "\t𐍈 city\n", "AC"),
)
LOCATIONS = (("00123", True), ("123", False), ("0", False), ("888", False))


def _order(index: int, status: str, clocks: tuple[datetime | None, ...]) -> tuple[object, ...]:
    purchase, approval, carrier, customer, _ = clocks
    optional = (approval, carrier, customer)
    comparisons = (
        (approval, purchase),
        (carrier, purchase),
        (customer, purchase),
        (carrier, approval),
        (customer, approval),
        (customer, carrier),
    )
    return (
        LOAD_A if index < 3 else LOAD_C,
        4294967297 if index == 0 else index + 1,
        TARGET_ID if index == 0 else str(index) * 32,
        CUSTOMER_IDS[index],
        status,
        *clocks,
        *(value is None for value in optional),
        *(status == "delivered" and value is None for value in optional),
        *(left is not None and right is not None and left < right for left, right in comparisons),
    )


ORDERS = (
    _order(0, "delivered", tuple(datetime(2018, 1, day) for day in range(1, 6))),
    _order(
        1, "delivered", (datetime(2016, 2, 29, 23, 59, 59), None, None, None, datetime(2016, 3, 2))
    ),
    _order(2, "delivered", tuple(datetime(2020, 4, day, 23, 59, 59) for day in range(9, 4, -1))),
    _order(
        3,
        "canceled",
        (
            datetime(2017, 12, 31, 23, 59, 59),
            datetime(2018, 1, 1),
            None,
            None,
            datetime(2018, 1, 3),
        ),
    ),
    _order(
        4,
        "unavailable",
        (datetime(2019, 12, 30), None, datetime(2019, 12, 31), None, datetime(2020, 1, 1)),
    ),
)
DATES = tuple(sorted({clock.date() for row in ORDERS for clock in row[5:10] if clock is not None}))


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_orders": "synthetic_orders",
        "int_order_customers": "synthetic_customers",
        "dim_customer": "synthetic_identities",
        "dim_location": "synthetic_locations",
        "dim_date": "synthetic_dates",
        "fact_orders": "synthetic_projection",
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


def _contract():
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load((PROJECT / "models/core/fact_orders.yml").read_text("utf-8"))[
        "models"
    ][0]
    assert contract["name"] == "fact_orders"
    assert contract["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(column["name"] for column in contract["columns"]) == COLUMNS
    assert tuple(column["data_type"] for column in contract["columns"]) == TYPES
    definitions = []
    for column in contract["columns"]:
        for definition in column.get("data_tests", []):
            name = definition if isinstance(definition, str) else next(iter(definition))
            arguments = {} if isinstance(definition, str) else definition[name]["arguments"]
            definitions.append((column["name"], name, arguments))
    assert len(definitions) == 30
    assert tuple(c for c, name, _ in definitions if name == "not_null") == REQUIRED
    assert [(c, name) for c, name, _ in definitions if name == "unique"] == [("order_id", "unique")]
    assert {
        c: tuple(args["values"]) for c, name, args in definitions if name == "accepted_values"
    } == {
        "order_status": STATUSES,
        "customer_state": STATES,
    }
    return definitions


def _generic_sql(column_name: str, name: str) -> str:
    arguments = next(
        args for column, test, args in _contract() if (column, test) == (column_name, name)
    )
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name, **arguments
    ).strip()


def _changed(rows, columns: tuple[str, ...], column: str, replacement: object):
    row = list(rows[0])
    row[columns.index(column)] = replacement
    return (tuple(row), *rows[1:])


def _expected(orders=ORDERS, customers=CUSTOMERS) -> Counter:
    rows = []
    for order in orders:
        matches = [
            customer for customer in customers if order[3] is not None and customer[2] == order[3]
        ]
        for customer in matches or [None]:
            enrichment = (*customer[3:7], *customer[:2]) if customer is not None else (None,) * 6
            calendar = tuple(clock.date() if clock is not None else None for clock in order[5:10])
            rows.append((*order, *enrichment, *calendar))
    return Counter(rows)


def _cte(
    *,
    orders=ORDERS,
    customers=CUSTOMERS,
    identities=IDENTITIES,
    locations=LOCATIONS,
    dates=DATES,
    source_collation: str | None = None,
    override: tuple[str, object] | None = None,
    mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert source_collation in {None, "C", "POSIX"}
    assert mode in {"same", "missing", "extra", "duplicate"}
    assert override is None or override[0] in COLUMNS and mode == "same"
    ctes, parameters = [], []
    for name, columns, types, rows in (
        ("orders", SOURCE_COLUMNS, SOURCE_TYPES, orders),
        ("customers", CUSTOMER_COLUMNS, CUSTOMER_TYPES, customers),
        ("identities", ("customer_unique_id",), ("text",), tuple((v,) for v in identities)),
        ("locations", ("zip_code_prefix", "has_geolocation"), ("text", "boolean"), locations),
        ("dates", ("calendar_date",), ("date",), tuple((v,) for v in dates)),
    ):
        assert len(rows) <= (24 if name == "dates" else 8)
        assert all(len(row) == len(columns) for row in rows)
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
    ctes.append("synthetic_actual as (" + _render("models/core/fact_orders.sql") + ")")
    fields = []
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                'case when order_id COLLATE "C"=%s::text COLLATE "C" then %s::'
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.extend((TARGET_ID, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += ' where order_id COLLATE "C" is distinct from %s::text COLLATE "C"'
        parameters.append(TARGET_ID)
    elif mode in {"extra", "duplicate"}:
        added = ["%s::text" if mode == "extra" and c == "order_id" else c for c in COLUMNS]
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
            "Fact-order native setup failed; inspect private local configuration.", pytrace=False
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


def _singular(connection: psycopg.Connection, name: str, **options: object):
    assert name in SINGULARS
    sql = _render("tests/" + name + ".sql")
    return _query(connection, "select * from (" + sql + ") diagnostics", **options).fetchall()


def _generic_count(connection: psycopg.Connection, column: str, name: str, **options: object):
    sql = _generic_sql(column, name)
    return _query(connection, "select count(*) from (" + sql + ") failures", **options).fetchone()[
        0
    ]


def _generic_counts(connection: psycopg.Connection, checks, **options: object):
    # Batch the YAML matrix into one bounded read-only query to limit round trips.
    checks = tuple(checks)
    expressions = [
        "(select count(*) from (" + _generic_sql(column, name) + ") failures)"
        for column, name in checks
    ]
    result = _query(connection, "select " + ", ".join(expressions), **options).fetchone()
    return dict(zip(checks, result, strict=True))


def _assert_shape(result) -> None:
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES


@pytest.mark.parametrize("source_collation", [None, "POSIX"])
@pytest.mark.parametrize("timezone", ["UTC", "Pacific/Honolulu"])
def test_actual_model_preserves_all_fields_literal_addresses_flags_and_naive_dates(
    transformer_connection: psycopg.Connection, source_collation: str | None, timezone: str
) -> None:
    assert timezone in {"UTC", "Pacific/Honolulu"}
    transformer_connection.execute("SET LOCAL TIME ZONE '" + timezone + "'")
    result = _query(
        transformer_connection, "select * from synthetic_actual", source_collation=source_collation
    )
    _assert_shape(result)
    assert Counter(result.fetchall()) == _expected()
    # The source and mapped text types/collations stay inherited from each input.
    equalities = []
    for column in ("order_id", "customer_id", "order_status"):
        equalities.append(
            "pg_collation_for(a."
            + column
            + ") IS NOT DISTINCT FROM pg_collation_for(o."
            + column
            + ")"
        )
    for column in MAPPED_COLUMNS[:4]:
        equalities.append(
            "pg_collation_for(a."
            + column
            + ") IS NOT DISTINCT FROM pg_collation_for(c."
            + column
            + ")"
        )
    assert _query(
        transformer_connection,
        "select bool_and(" + " AND ".join(equalities) + ") from synthetic_actual a "
        'join synthetic_orders o on a.order_id COLLATE "C"=o.order_id COLLATE "C" '
        'join synthetic_customers c on a.customer_id COLLATE "C"=c.customer_id COLLATE "C"',
        source_collation=source_collation,
    ).fetchone() == (True,)
    for name in SINGULARS:
        assert _singular(transformer_connection, name, source_collation=source_collation) == []


def test_every_actual_yaml_configured_generic_accepts_the_complete_synthetic_fact(
    transformer_connection: psycopg.Connection,
) -> None:
    checks = tuple((column, name) for column, name, _ in _contract())
    assert _generic_counts(transformer_connection, checks) == dict.fromkeys(checks, 0)


def test_each_required_output_null_is_blocked_by_actual_yaml_macro(
    transformer_connection: psycopg.Connection,
) -> None:
    checks = tuple((column, "not_null") for column in REQUIRED)
    assert _generic_counts(
        transformer_connection, checks, orders=((None,) * len(SOURCE_COLUMNS),)
    ) == dict.fromkeys(checks, 1)


@pytest.mark.parametrize("column", CLOCKS[1:4])
def test_nullable_lifecycle_clock_and_date_remain_null_without_losing_order(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    orders = _changed(ORDERS, SOURCE_COLUMNS, column, None)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == _expected(orders)
    # Fact construction preserves upstream flags even when a synthetic parent is inconsistent.
    for name in SINGULARS:
        assert _singular(transformer_connection, name, orders=orders) == []


@pytest.mark.parametrize(
    "column", ("_load_id", "order_purchase_timestamp", "order_estimated_delivery_date")
)
def test_invalid_required_parent_null_is_retained_and_blocked_without_order_filter(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    orders = _changed(ORDERS, SOURCE_COLUMNS, column, None)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", orders=orders).fetchall()
    ) == _expected(orders)
    assert _generic_count(transformer_connection, column, "not_null", orders=orders) == 1
    assert (
        _singular(transformer_connection, "fact_orders_source_reconciliation", orders=orders) == []
    )


@pytest.mark.parametrize("duplicate_kind", ["identical", "conflicting"])
def test_duplicate_mapping_fanout_fails_independent_count_and_order_unique(
    transformer_connection: psycopg.Connection, duplicate_kind: str
) -> None:
    duplicate = (
        CUSTOMERS[0]
        if duplicate_kind == "identical"
        else (LOAD_C, 2, *CUSTOMERS[0][2:5], "Other city", "RJ")
    )
    customers = (*CUSTOMERS, duplicate)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == _expected(customers=customers)
    assert _singular(
        transformer_connection, "fact_orders_source_reconciliation", customers=customers
    ) == [(5, 6, 0, 0)]
    assert _generic_count(transformer_connection, "order_id", "unique", customers=customers) == 1


def test_missing_mapping_retains_order_with_null_enrichment_and_blocks_references(
    transformer_connection: psycopg.Connection,
) -> None:
    customers = CUSTOMERS[1:]
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == _expected(customers=customers)
    assert (
        _singular(transformer_connection, "fact_orders_source_reconciliation", customers=customers)
        == []
    )
    assert _singular(transformer_connection, "fact_orders_relationships", customers=customers) == [
        (1, 1, 1, 0)
    ]
    assert _singular(transformer_connection, "fact_orders_domains", customers=customers) == [(1,)]
    checks = tuple((column, "not_null") for column in MAPPED_COLUMNS)
    assert _generic_counts(transformer_connection, checks, customers=customers) == dict.fromkeys(
        checks, 1
    )


@pytest.mark.parametrize(
    "literal", ["A" * 32, " " + CUSTOMER_IDS[0], CUSTOMER_IDS[0] + " ", "ａ" * 32, "𐍈" * 32]
)
def test_mapping_lookup_uses_literal_customer_key_without_case_space_unicode_conversion(
    transformer_connection: psycopg.Connection, literal: str
) -> None:
    customers = _changed(CUSTOMERS, CUSTOMER_COLUMNS, "customer_id", literal)
    assert Counter(
        _query(
            transformer_connection, "select * from synthetic_actual", customers=customers
        ).fetchall()
    ) == _expected(customers=customers)
    assert _singular(transformer_connection, "fact_orders_relationships", customers=customers) == [
        (1, 1, 1, 0)
    ]


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("order_id", "A" * 32),
        ("order_id", TARGET_ID + " "),
        ("order_id", "ａ" * 32),
        ("customer_id", "A" * 32),
        ("customer_id", " " + CUSTOMER_IDS[0]),
        ("customer_id", "ａ" * 32),
        ("customer_unique_id", "A" * 32),
        ("customer_unique_id", IDENTITIES[0] + " "),
        ("customer_unique_id", "ａ" * 32),
        ("customer_zip_code_prefix", "１２３"),
        ("customer_zip_code_prefix", "1 2"),
        ("customer_zip_code_prefix", "000123"),
        ("customer_zip_code_prefix", ""),
        ("_source_row", 0),
        ("customer_source_row", 0),
    ],
)
def test_actual_model_retains_invalid_literal_domain_inputs_for_blocking_validation(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    orders, customers = ORDERS, CUSTOMERS
    if column in SOURCE_COLUMNS:
        orders = _changed(orders, SOURCE_COLUMNS, column, replacement)
        if column == "customer_id":
            customers = _changed(customers, CUSTOMER_COLUMNS, "customer_id", replacement)
    else:
        source_name = "_source_row" if column == "customer_source_row" else column
        customers = _changed(customers, CUSTOMER_COLUMNS, source_name, replacement)
    options = {"orders": orders, "customers": customers}
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
    ) == _expected(orders, customers)
    assert _singular(transformer_connection, "fact_orders_domains", **options) == [(1,)]
    assert _singular(transformer_connection, "fact_orders_source_reconciliation", **options) == []


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("order_status", "Delivered"),
        ("order_status", " delivered "),
        ("order_status", "invalid"),
        ("customer_state", "sp"),
        ("customer_state", " SP "),
        ("customer_state", "ＳＰ"),
    ],
)
def test_actual_yaml_accepted_domains_reject_literal_status_state_without_normalization(
    transformer_connection: psycopg.Connection, column: str, replacement: str
) -> None:
    options = (
        {"orders": _changed(ORDERS, SOURCE_COLUMNS, column, replacement)}
        if column == "order_status"
        else {"customers": _changed(CUSTOMERS, CUSTOMER_COLUMNS, column, replacement)}
    )
    assert _generic_count(transformer_connection, column, "accepted_values", **options) == 1
    assert _singular(transformer_connection, "fact_orders_source_reconciliation", **options) == []


MUTATIONS = (
    LOAD_C,
    1,
    "f" * 32,
    CUSTOMER_IDS[1],
    "approved",
    *(datetime(2021, 7, day) for day in range(1, 6)),
    *(not value for value in ORDERS[0][10:22]),
    IDENTITIES[1],
    "123",
    "São Paulo",
    "RJ",
    LOAD_C,
    1,
    *(date(2021, 7, day) for day in range(1, 6)),
)


@pytest.mark.parametrize("column,replacement", list(zip(COLUMNS, MUTATIONS, strict=True)))
def test_full_reconciliation_blocks_mutation_of_each_of_33_fields_at_constant_count(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "fact_orders_source_reconciliation", override=(column, replacement)
    ) == [(5, 5, 1, 1)]


@pytest.mark.parametrize(
    "mode,diagnostics",
    [("missing", (5, 4, 1, 0)), ("extra", (5, 6, 0, 1)), ("duplicate", (5, 6, 0, 1))],
)
def test_full_reconciliation_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str, diagnostics: tuple[int, ...]
) -> None:
    assert _singular(transformer_connection, "fact_orders_source_reconciliation", mode=mode) == [
        diagnostics
    ]
    if mode == "duplicate":
        assert _generic_count(transformer_connection, "order_id", "unique", mode=mode) == 1


@pytest.mark.parametrize("column", DATE_COLUMNS)
@pytest.mark.parametrize("replacement", [None, date(2030, 1, 1)])
def test_each_date_role_mismatch_blocks_domain_reconciliation_and_nonnull_missing_parent(
    transformer_connection: psycopg.Connection, column: str, replacement: date | None
) -> None:
    options = {"override": (column, replacement)}
    assert _singular(transformer_connection, "fact_orders_domains", **options) == [(1,)]
    assert _singular(transformer_connection, "fact_orders_source_reconciliation", **options) == [
        (5, 5, 1, 1)
    ]
    assert _singular(transformer_connection, "fact_orders_relationships", **options) == (
        [] if replacement is None else [(0, 0, 0, 1)]
    )


@pytest.mark.parametrize("column", DATE_COLUMNS)
def test_every_recorded_date_role_requires_parent_without_order_loss(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    required_date = ORDERS[0][5 + DATE_COLUMNS.index(column)].date()
    dates = tuple(value for value in DATES if value != required_date)
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", dates=dates).fetchall()
        )
        == _expected()
    )
    assert _singular(transformer_connection, "fact_orders_relationships", dates=dates) == [
        (0, 0, 0, 1)
    ]
    assert _singular(transformer_connection, "fact_orders_source_reconciliation", dates=dates) == []


@pytest.mark.parametrize("parent", ["identity", "zip"])
def test_identity_and_literal_zip_parent_existence_blocks_without_geography_filter(
    transformer_connection: psycopg.Connection, parent: str
) -> None:
    options = (
        {"identities": IDENTITIES[1:]} if parent == "identity" else {"locations": LOCATIONS[1:]}
    )
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        )
        == _expected()
    )
    assert _singular(transformer_connection, "fact_orders_relationships", **options) == [
        (0, 3, 0, 0) if parent == "identity" else (0, 0, 1, 0)
    ]


def test_duplicate_dimension_parents_do_not_multiply_fact_or_choose_addresses(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {
        "identities": (*IDENTITIES, IDENTITIES[0]),
        "locations": (*LOCATIONS, LOCATIONS[0]),
        "dates": (*DATES, DATES[0]),
    }
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        )
        == _expected()
    )
    for name in SINGULARS:
        assert _singular(transformer_connection, name, **options) == []


def test_empty_source_has_all_33_typed_fields_and_zero_failures(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {"orders": (), "customers": (), "identities": (), "locations": (), "dates": ()}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert result.fetchall() == []
    for name in SINGULARS:
        assert _singular(transformer_connection, name, **options) == []
    checks = tuple((column, name) for column, name, _ in _contract())
    assert _generic_counts(transformer_connection, checks, **options) == dict.fromkeys(checks, 0)


def test_all_null_parent_retains_one_typed_order_and_blocks_required_domains_and_parents(
    transformer_connection: psycopg.Connection,
) -> None:
    orders = ((None,) * len(SOURCE_COLUMNS),)
    result = _query(transformer_connection, "select * from synthetic_actual", orders=orders)
    _assert_shape(result)
    assert result.fetchall() == [(None,) * len(COLUMNS)]
    assert (
        _singular(transformer_connection, "fact_orders_source_reconciliation", orders=orders) == []
    )
    assert _singular(transformer_connection, "fact_orders_domains", orders=orders) == [(1,)]
    assert _singular(transformer_connection, "fact_orders_relationships", orders=orders) == [
        (1, 1, 1, 0)
    ]
