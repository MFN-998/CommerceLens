"""Opt-in, aggregate-only physical acceptance of the private order fact view.

Independent guarded raw expectations conserve every order, customer address and
both source lineages. No source records are fetched or exposed in assertions, and
the transaction cannot create or persist database objects.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_ORDERS_INTEGRATION") != "1",
    reason="Built order-fact checks require explicit opt-in",
)

TIMESTAMPS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
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
ORDER_COLUMNS = ("_load_id", "_source_row", "order_id", "customer_id", "order_status") + (
    TIMESTAMPS + FLAGS
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
MAPPING_COLUMNS = CUSTOMER_COLUMNS[3:] + ("customer_load_id", "customer_source_row")
DATE_COLUMNS = (
    "purchase_calendar_date",
    "approval_calendar_date",
    "carrier_delivery_calendar_date",
    "customer_delivery_calendar_date",
    "estimated_delivery_calendar_date",
)
COLUMNS = ORDER_COLUMNS + MAPPING_COLUMNS + DATE_COLUMNS
TYPES = (
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
TEXT_COLUMNS = set(ORDER_COLUMNS[2:5] + CUSTOMER_COLUMNS[2:])
STATUSES = (
    "created",
    "approved",
    "invoiced",
    "processing",
    "shipped",
    "delivered",
    "unavailable",
    "canceled",
)
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
REQUIRED_COLUMNS = (
    ORDER_COLUMNS[:6]
    + (TIMESTAMPS[-1],)
    + FLAGS
    + MAPPING_COLUMNS
    + (DATE_COLUMNS[0], DATE_COLUMNS[-1])
)
FLAG_COUNTS = (160, 1783, 2965, 14, 2, 8, 0, 166, 0, 1359, 61, 23)
TIMESTAMP_COUNTS = (99441, 99281, 97658, 96476, 99441)


def _fields(columns: tuple[str, ...], *, raw: bool = False) -> str:
    fields = []
    for column in columns:
        expression = f"nullif({column}, '')" if raw and column in TEXT_COLUMNS else column
        if column in TEXT_COLUMNS:
            expression += ' COLLATE "C"'
        fields.append(f"{expression} AS {column}")
    return ", ".join(fields)


def _valid_timestamp(column: str) -> str:
    # This independent expression mirrors the accepted source domain. The
    # calendar check rejects impossible dates before any timestamp cast occurs.
    return (
        f"({column} ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) "
        "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' "
        f"AND pg_input_is_valid({column}, 'timestamp without time zone') "
        f'AND {column} COLLATE "C" BETWEEN '
        "'1677-09-21 00:12:44' AND '2262-04-11 23:47:16')"
    )


def _raw_orders_ctes() -> str:
    normalized = ", ".join(
        column if index < 2 else f"nullif({column}, '') AS {column}"
        for index, column in enumerate(ORDER_COLUMNS[:10])
    )
    typed = (
        _fields(ORDER_COLUMNS[:5])
        + ", "
        + ", ".join(
            f"CAST(CASE WHEN {_valid_timestamp(column)} THEN {column} END "
            f"AS timestamp without time zone) AS {column}"
            for column in TIMESTAMPS
        )
    )
    missing = ", ".join(
        f"{column} IS NULL AS {flag}"
        for column, flag in zip(TIMESTAMPS[1:4], FLAGS[:3], strict=True)
    )
    delivered = ", ".join(
        f"COALESCE(order_status = 'delivered' AND {column} IS NULL, false) AS {flag}"
        for column, flag in zip(TIMESTAMPS[1:4], FLAGS[3:6], strict=True)
    )
    reversals = ", ".join(
        f"COALESCE({left} < {right}, false) AS {flag}"
        for (left, right), flag in zip(
            (
                (TIMESTAMPS[1], TIMESTAMPS[0]),
                (TIMESTAMPS[2], TIMESTAMPS[0]),
                (TIMESTAMPS[3], TIMESTAMPS[0]),
                (TIMESTAMPS[2], TIMESTAMPS[1]),
                (TIMESTAMPS[3], TIMESTAMPS[1]),
                (TIMESTAMPS[3], TIMESTAMPS[2]),
            ),
            FLAGS[6:],
            strict=True,
        )
    )
    return (
        f"raw_normalized AS MATERIALIZED (SELECT {normalized} FROM raw.orders), "
        f"raw_typed AS MATERIALIZED (SELECT {typed}, {missing} FROM raw_normalized), "
        f"raw_orders AS MATERIALIZED (SELECT *, {delivered}, {reversals} FROM raw_typed)"
    )


def _fact_projection(orders: str, customers: str) -> str:
    orders_fields = ", ".join(f"o.{column}" for column in ORDER_COLUMNS)
    customers_fields = ", ".join(f"c.{column}" for column in CUSTOMER_COLUMNS[3:])
    dates = ", ".join(
        f"CAST(o.{timestamp} AS date) AS {date}"
        for timestamp, date in zip(TIMESTAMPS, DATE_COLUMNS, strict=True)
    )
    return (
        f"SELECT {orders_fields}, {customers_fields}, c._load_id AS customer_load_id, "
        f"c._source_row AS customer_source_row, {dates} FROM {orders} o "
        f'LEFT JOIN {customers} c ON o.customer_id COLLATE "C"=c.customer_id COLLATE "C"'
    )


def _source_ctes() -> str:
    return (
        "WITH " + _raw_orders_ctes() + ", "
        f"raw_customers AS MATERIALIZED (SELECT {_fields(CUSTOMER_COLUMNS, raw=True)} "
        "FROM raw.customers), "
        f"staged_orders AS MATERIALIZED (SELECT {_fields(ORDER_COLUMNS)} "
        "FROM staging.stg_orders), "
        f"staged_customers AS MATERIALIZED (SELECT {_fields(CUSTOMER_COLUMNS)} "
        "FROM staging.stg_customers), "
        f"mapped_customers AS MATERIALIZED (SELECT {_fields(CUSTOMER_COLUMNS)} "
        "FROM core.int_order_customers), "
        f"raw_expected AS MATERIALIZED ({_fact_projection('raw_orders', 'raw_customers')}), "
        "staged_expected AS MATERIALIZED ("
        + _fact_projection("staged_orders", "mapped_customers")
        + "), "
        f"actual AS MATERIALIZED (SELECT {_fields(COLUMNS)} FROM core.fact_orders) "
    )


@pytest.fixture
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
    except Exception:  # noqa: BLE001 - setup failures must not reveal private connection details.
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Order-fact physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def _diagnostic(
    connection: psycopg.Connection,
    query: str,
    params: tuple[object, ...] | None = None,
    *,
    binary: bool = True,
) -> psycopg.Cursor:
    try:
        return connection.execute(query, params, binary=binary)
    except psycopg.Error:
        pytest.fail(
            "Order-fact physical diagnostic query failed; inspect private local configuration.",
            pytrace=False,
        )


def test_fact_order_session_native_types_lineage_collations_and_private_access(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    assert _diagnostic(
        connection,
        "SELECT session_user, current_user, current_database(), "
        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())",
    ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
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
    _diagnostic(connection, "SET LOCAL ROLE commercelens_transformer")
    assert _diagnostic(
        connection, "SELECT current_user, current_setting('transaction_read_only')"
    ).fetchone() == ("commercelens_transformer", "on")
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.orders', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.orders', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
        "has_table_privilege(current_user, 'raw.customers', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.customers', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
    ).fetchone() == (True, False, True, True, True, True, False, True, False)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='fact_orders'",
    ).fetchone() == ("v", "commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.fact_orders'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))

    inherited = tuple((name, "staging.stg_orders", name) for name in ORDER_COLUMNS) + tuple(
        (name, "core.int_order_customers", source)
        for name, source in zip(
            MAPPING_COLUMNS, CUSTOMER_COLUMNS[3:] + CUSTOMER_COLUMNS[:2], strict=True
        )
    )
    inherited_values = ", ".join("(%s::text,%s::text,%s::text)" for _ in inherited)
    assert _diagnostic(
        connection,
        "WITH inherited(fact_name, source_relation, source_name) AS (VALUES "
        + inherited_values
        + ") SELECT count(*), bool_and(a.atttypid=s.atttypid AND a.atttypmod=s.atttypmod "
        "AND a.attcollation=s.attcollation) FROM inherited i JOIN pg_attribute a "
        "ON a.attrelid='core.fact_orders'::regclass AND a.attname=i.fact_name "
        "AND a.attnum>0 AND NOT a.attisdropped JOIN pg_attribute s "
        "ON s.attrelid=to_regclass(i.source_relation) AND s.attname=i.source_name "
        "AND s.attnum>0 AND NOT s.attisdropped",
        tuple(value for row in inherited for value in row),
    ).fetchone() == (28, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.fact_orders', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')",
    ).fetchone() == (4, True)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('fact_orders__dbt_tmp','fact_orders__dbt_backup')",
    ).fetchone() == (0,)


def test_fact_order_independent_source_multisets_flags_dates_and_parent_coverage(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    _diagnostic(connection, "SET LOCAL ROLE commercelens_transformer")
    assert _diagnostic(
        connection, "SELECT current_user, current_setting('transaction_read_only')"
    ).fetchone() == ("commercelens_transformer", "on")

    counts: list[tuple[str, str, int]] = []
    for relation in (
        "raw_orders",
        "staged_orders",
        "raw_customers",
        "staged_customers",
        "mapped_customers",
        "raw_expected",
        "staged_expected",
        "actual",
    ):
        counts.append((relation + "_count", f"SELECT count(*) FROM {relation}", 99441))
    for relation in ("raw_orders", "staged_orders", "actual"):
        counts.append(
            (relation + "_order_ids", f"SELECT count(DISTINCT order_id) FROM {relation}", 99441)
        )
    for relation in ("raw_customers", "staged_customers", "mapped_customers", "actual"):
        counts.extend(
            (
                (
                    relation + "_customer_ids",
                    f"SELECT count(DISTINCT customer_id) FROM {relation}",
                    99441,
                ),
                (
                    relation + "_identities",
                    f"SELECT count(DISTINCT customer_unique_id) FROM {relation}",
                    96096,
                ),
            )
        )
    for left, right in (
        ("raw_orders", "staged_orders"),
        ("raw_customers", "staged_customers"),
        ("staged_customers", "mapped_customers"),
        ("raw_customers", "mapped_customers"),
        ("raw_expected", "staged_expected"),
        ("staged_expected", "actual"),
        ("raw_expected", "actual"),
    ):
        for expected, observed in ((left, right), (right, left)):
            counts.append(
                (
                    expected + "_minus_" + observed,
                    (
                        f"SELECT count(*) FROM (SELECT * FROM {expected} EXCEPT ALL "
                        f"SELECT * FROM {observed}) differences"
                    ),
                    0,
                )
            )
    invalid_clock = " OR ".join(
        f"({column} IS NOT NULL AND NOT {_valid_timestamp(column)})" for column in TIMESTAMPS
    )
    counts.append(
        (
            "invalid_nonempty_raw_clocks",
            f"SELECT count(*) FROM raw_normalized WHERE {invalid_clock}",
            0,
        )
    )
    result = _diagnostic(
        connection,
        _source_ctes() + "SELECT " + ", ".join(f"({query})" for _, query, _ in counts),
        binary=True,
    ).fetchone()
    assert result is not None
    assert dict(zip((name for name, _, _ in counts), result, strict=True)) == {
        name: expected for name, _, expected in counts
    }

    # Every source flag and nullable timestamp survives exactly. Missingness is
    # based on normalized raw text, independently of guarded timestamp parsing.
    flag_aggregates = ", ".join(f"count(*) FILTER (WHERE {flag})" for flag in FLAGS)
    timestamp_aggregates = ", ".join(f"count({column})" for column in TIMESTAMPS)
    assert (
        _diagnostic(
            connection,
            _source_ctes()
            + " UNION ALL ".join(
                f"SELECT {flag_aggregates}, {timestamp_aggregates} FROM {relation}"
                for relation in ("raw_orders", "staged_orders", "actual")
            ),
            binary=True,
        ).fetchall()
        == [FLAG_COUNTS + TIMESTAMP_COUNTS] * 3
    )

    date_mismatch = " OR ".join(
        f"{date} IS DISTINCT FROM CAST({timestamp} AS date)"
        for timestamp, date in zip(TIMESTAMPS, DATE_COLUMNS, strict=True)
    )
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM core.fact_orders WHERE "
        + " OR ".join(column + " IS NULL" for column in REQUIRED_COLUMNS)
        + " OR order_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR customer_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR customer_unique_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR customer_zip_code_prefix COLLATE \"C\" !~ '^[0-9]{1,5}$' "
        "OR _source_row<1 OR customer_source_row<1 "
        'OR order_status COLLATE "C"<>ALL(%s::text[]) '
        'OR customer_state COLLATE "C"<>ALL(%s::text[]) OR ' + date_mismatch,
        (list(STATUSES), list(STATES)),
        binary=True,
    ).fetchone() == (0,)
    observed_dates = " UNION ALL ".join(
        f"SELECT {column} AS calendar_date FROM core.fact_orders" for column in DATE_COLUMNS
    )
    assert _diagnostic(
        connection,
        "WITH observed_dates AS (" + observed_dates + "), "
        "required_dates AS MATERIALIZED (SELECT DISTINCT calendar_date FROM observed_dates "
        "WHERE calendar_date IS NOT NULL), "
        "raw_geography AS MATERIALIZED ("
        "SELECT DISTINCT nullif(geolocation_zip_code_prefix,'') COLLATE \"C\" AS zip "
        "FROM raw.geolocation) "
        "SELECT (SELECT count(*) FROM core.fact_orders f WHERE NOT EXISTS ("
        'SELECT 1 FROM core.int_order_customers c WHERE f.customer_id COLLATE "C"='
        'c.customer_id COLLATE "C")), '
        "(SELECT count(*) FROM core.fact_orders f WHERE NOT EXISTS ("
        'SELECT 1 FROM core.dim_customer d WHERE f.customer_unique_id COLLATE "C"='
        'd.customer_unique_id COLLATE "C")), '
        "(SELECT count(*) FROM core.fact_orders f WHERE NOT EXISTS ("
        'SELECT 1 FROM core.dim_location d WHERE f.customer_zip_code_prefix COLLATE "C"='
        'd.zip_code_prefix COLLATE "C")), '
        "(SELECT count(*) FROM required_dates r WHERE NOT EXISTS ("
        "SELECT 1 FROM core.dim_date d WHERE r.calendar_date=d.calendar_date)), "
        "(SELECT count(*) FROM core.fact_orders f WHERE EXISTS ("
        'SELECT 1 FROM core.dim_location d WHERE f.customer_zip_code_prefix COLLATE "C"='
        'd.zip_code_prefix COLLATE "C" AND NOT d.has_geolocation)), '
        "(SELECT count(*) FROM core.fact_orders f WHERE NOT EXISTS ("
        'SELECT 1 FROM raw_geography g WHERE f.customer_zip_code_prefix COLLATE "C"=g.zip)), '
        "(SELECT count(*) FROM core.fact_orders f WHERE EXISTS ("
        'SELECT 1 FROM core.dim_location d WHERE f.customer_zip_code_prefix COLLATE "C"='
        'd.zip_code_prefix COLLATE "C" AND d.has_geolocation IS NULL))',
        binary=True,
    ).fetchone() == (0, 0, 0, 0, 278, 278, 0)
