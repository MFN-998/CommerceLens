"""Opt-in read-only physical acceptance using metadata and aggregate evidence.

Compare all eight clocks including NULLs and lineage before deriving dates. Safe
raw parsing is independent of dbt macros. No source records or identifiers leave
SQL; fetched diagnostics are counts and booleans only.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_DATE_DIMENSION_INTEGRATION") != "1",
    reason="Built date dimension checks require explicit opt-in",
)

COLUMNS = (
    "calendar_date",
    "calendar_year",
    "calendar_quarter",
    "calendar_month",
    "day_of_month",
    "iso_year",
    "iso_week",
    "iso_day_of_week",
    "is_weekend",
)
TYPES = ("date", *("integer",) * 7, "boolean")
CLOCKS = {
    "orders": (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    "order_items": ("shipping_limit_date",),
    "order_reviews": ("review_creation_date", "review_answer_timestamp"),
}


def _event_inputs(schema: str, *, raw: bool) -> str:
    assert schema in {"raw", "staging"} and raw == (schema == "raw")
    queries = []
    for table, columns in CLOCKS.items():
        values = ", ".join(
            "('"
            + table
            + "."
            + column
            + "', "
            + ("nullif(s." + column + ",'')" if raw else "s." + column)
            + ")"
            for column in columns
        )
        relation = schema + "." + (table if raw else "stg_" + table)
        queries.append(
            "SELECT v.source_event, s._load_id, s._source_row, v.event_value FROM "
            + relation
            + " s CROSS JOIN LATERAL (VALUES "
            + values
            + ") v(source_event, event_value)"
        )
    return " UNION ALL ".join(queries)


def _raw_timestamp() -> str:
    # Guard the operand before casting: rejected calendar text must never raise
    # or silently enter the observed-date domain. Grammar/bounds match the
    # accepted Phase 2/warehouse timestamp contract, without invoking its macro.
    return (
        "CAST(CASE WHEN event_value ~ "
        "'^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) "
        "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' "
        "AND pg_input_is_valid(event_value, 'timestamp without time zone') "
        'AND event_value COLLATE "C" BETWEEN '
        "'1677-09-21 00:12:44' AND '2262-04-11 23:47:16' "
        "THEN event_value END AS timestamp without time zone)"
    )


def _calendar_projection() -> str:
    return (
        "SELECT calendar_date, EXTRACT(year FROM calendar_date)::integer AS calendar_year, "
        "EXTRACT(quarter FROM calendar_date)::integer AS calendar_quarter, "
        "EXTRACT(month FROM calendar_date)::integer AS calendar_month, "
        "EXTRACT(day FROM calendar_date)::integer AS day_of_month, "
        "EXTRACT(isoyear FROM calendar_date)::integer AS iso_year, "
        "EXTRACT(week FROM calendar_date)::integer AS iso_week, "
        "EXTRACT(isodow FROM calendar_date)::integer AS iso_day_of_week, "
        "EXTRACT(isodow FROM calendar_date) IN (6,7) AS is_weekend FROM staged_dates"
    )


@pytest.fixture
def transformer_connection() -> Iterator[psycopg.Connection]:
    stack = ExitStack()
    try:
        connection = stack.enter_context(connect(load_settings(purpose="transformer")))
        assert connection.info.get_parameters().get("sslmode") == "verify-full"
        stack.enter_context(connection.transaction())
        connection.execute("SET TRANSACTION READ ONLY")
    except Exception:
        with suppress(Exception):
            stack.close()
        pytest.fail(
            "Date dimension physical setup failed; inspect private local configuration.",
            pytrace=False,
        )
    try:
        yield connection
    finally:
        stack.close()


def test_date_types_ownership_session_private_access_and_complete_source_conservation(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    assert connection.execute(
        "SELECT session_user, current_user, current_database(), "
        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
    ).fetchone() == ("commercelens_transform", "commercelens_transform", "postgres", True)
    assert connection.execute(
        "SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname=session_user"
    ).fetchone() == (True, False, False, False, False, False, False, 2)
    assert connection.execute(
        "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
        "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
        "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=session_user"
    ).fetchall() == [("commercelens_transformer", False, False, True)]
    connection.execute("SET LOCAL ROLE commercelens_transformer")
    assert connection.execute(
        "SELECT current_user, current_setting('transaction_read_only')"
    ).fetchone() == ("commercelens_transformer", "on")
    assert connection.execute(
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE')"
    ).fetchone() == (True, False, True, True, True)
    for table in CLOCKS:
        assert connection.execute(
            "SELECT has_table_privilege(current_user, %s, 'SELECT'), "
            "has_table_privilege(current_user, %s, "
            "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
            ("raw." + table, "raw." + table),
        ).fetchone() == (True, False)
    assert connection.execute(
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='dim_date'"
    ).fetchone() == ("v", "commercelens_transformer")
    assert connection.execute(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a WHERE a.attrelid='core.dim_date'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))
    for table, columns in CLOCKS.items():
        assert connection.execute(
            "SELECT count(*), bool_and(a.atttypid='timestamp without time zone'::regtype) "
            "FROM pg_attribute a WHERE a.attrelid=to_regclass(%s) "
            "AND a.attname::text=ANY(%s::text[]) AND NOT a.attisdropped",
            ("staging.stg_" + table, list(columns)),
        ).fetchone() == (len(columns), True)

    # Full per-event multisets retain NULLs and lineage. Invalid nonempty raw
    # timestamps are separately counted, so equal NULLs cannot conceal rejection.
    event_fields = 'source_event COLLATE "C", _load_id, _source_row, event_value'
    counts = connection.execute(
        "WITH raw_inputs AS MATERIALIZED (" + _event_inputs("raw", raw=True) + "), "
        "raw_events AS MATERIALIZED (SELECT source_event, _load_id, _source_row, "
        + _raw_timestamp()
        + " AS event_value, event_value IS NOT NULL AS has_raw_value "
        "FROM raw_inputs), staged_events AS MATERIALIZED ("
        + _event_inputs("staging", raw=False)
        + "), "
        "raw_missing AS (SELECT "
        + event_fields
        + " FROM raw_events EXCEPT ALL SELECT "
        + event_fields
        + " FROM staged_events), raw_extra AS (SELECT "
        + event_fields
        + " FROM staged_events EXCEPT ALL SELECT "
        + event_fields
        + " FROM raw_events), "
        "raw_dates AS MATERIALIZED (SELECT DISTINCT event_value::date AS calendar_date "
        "FROM raw_events WHERE event_value IS NOT NULL), staged_dates AS MATERIALIZED ("
        "SELECT DISTINCT event_value::date AS calendar_date FROM staged_events "
        "WHERE event_value IS NOT NULL), raw_date_missing AS ("
        "SELECT * FROM raw_dates EXCEPT ALL SELECT * FROM staged_dates), raw_date_extra AS ("
        "SELECT * FROM staged_dates EXCEPT ALL SELECT * FROM raw_dates), "
        "expected AS MATERIALIZED (" + _calendar_projection() + "), "
        "actual AS MATERIALIZED (SELECT " + ", ".join(COLUMNS) + " FROM core.dim_date), "
        "missing AS (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual), "
        "extra AS (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected) "
        "SELECT (SELECT count(*) FROM raw_events), (SELECT count(*) FROM staged_events), "
        "(SELECT count(*) FROM raw_events WHERE has_raw_value AND event_value IS NULL), "
        "(SELECT count(*) FROM raw_events WHERE event_value IS NOT NULL), "
        "(SELECT count(*) FROM staged_events WHERE event_value IS NOT NULL), "
        "(SELECT count(*) FROM raw_missing), (SELECT count(*) FROM raw_extra), "
        "(SELECT count(*) FROM raw_dates), (SELECT count(*) FROM staged_dates), "
        "(SELECT count(*) FROM actual), (SELECT count(DISTINCT calendar_date) FROM actual), "
        "(SELECT count(*) FROM raw_date_missing), (SELECT count(*) FROM raw_date_extra), "
        "(SELECT count(*) FROM missing), (SELECT count(*) FROM extra), "
        "(SELECT min(calendar_date)=date '2016-09-04' FROM actual), "
        "(SELECT max(calendar_date)=date '2020-04-09' FROM actual)",
        binary=True,
    ).fetchone()
    # Historical accepted snapshot and Oct 04 read-only preflight: all event
    # clocks, including warning dates, yield 803,395 timestamps / 755 dates.
    assert counts == (
        808303,
        808303,
        0,
        803395,
        803395,
        0,
        0,
        755,
        755,
        755,
        755,
        0,
        0,
        0,
        0,
        True,
        True,
    )
    assert connection.execute(
        "SELECT (SELECT count(*) FROM raw.orders), "
        "(SELECT count(*) FROM staging.stg_orders), "
        "(SELECT count(*) FROM raw.order_items), "
        "(SELECT count(*) FROM staging.stg_order_items), "
        "(SELECT count(*) FROM raw.order_reviews), "
        "(SELECT count(*) FROM staging.stg_order_reviews)"
    ).fetchone() == (99441, 99441, 112650, 112650, 99224, 99224)
    assert connection.execute(
        "SELECT count(*) FROM core.dim_date WHERE "
        + " OR ".join(column + " IS NULL" for column in COLUMNS)
    ).fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*), bool_and("
        "NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') AND "
        "NOT has_table_privilege(rolname, 'core.dim_date', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')"
    ).fetchone() == (4, True)
    assert connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('dim_date__dbt_tmp','dim_date__dbt_backup')"
    ).fetchone() == (0,)
