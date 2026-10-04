"""Opt-in aggregate-only physical acceptance of the private review fact view.

Independent guarded raw expectations conserve comments, events, warnings and
lineage across staging/core. Only counts and metadata leave read-only queries;
no source records or sensitive connection errors are fetched or reported.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, suppress

import psycopg
import pytest

from src.warehouse.config import connect, load_settings

pytestmark = pytest.mark.skipif(
    os.getenv("COMMERCE_WAREHOUSE_FACT_REVIEWS_INTEGRATION") != "1",
    reason="Built review-fact checks require explicit opt-in",
)

SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
    "is_answer_before_creation",
)
DATE_COLUMNS = ("review_creation_calendar_date", "review_answer_calendar_date")
COLUMNS = (*SOURCE_COLUMNS, *DATE_COLUMNS)
TYPES = (
    "uuid",
    "bigint",
    "text",
    "text",
    "bigint",
    "text",
    "text",
    "timestamp without time zone",
    "timestamp without time zone",
    "boolean",
    "date",
    "date",
)
REQUIRED = tuple(column for column in COLUMNS if column not in SOURCE_COLUMNS[5:7])
TEXT_COLUMNS = {"review_id", "order_id", "review_comment_title", "review_comment_message"}
CLOCKS = SOURCE_COLUMNS[7:9]
LOWER = "1677-09-21 00:12:44"
UPPER = "2262-04-11 23:47:16"
DECIMAL_PATTERN = "^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$"


def _fields(columns) -> str:
    return ", ".join(
        (column + ' COLLATE "C"' if column in TEXT_COLUMNS else column) + " AS " + column
        for column in columns
    )


def _valid_score(column: str) -> str:
    return (
        f"({column} IS NOT NULL AND {column}=trunc({column}) "
        f"AND {column} BETWEEN -9223372036854775808 AND 9223372036854775807)"
    )


def _valid_timestamp(column: str) -> str:
    return (
        f"({column} ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) "
        "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$' "
        f"AND pg_input_is_valid({column}, 'timestamp without time zone') "
        f"AND {column} COLLATE \"C\" BETWEEN '{LOWER}' AND '{UPPER}')"
    )


def _date_fields() -> str:
    return ", ".join(
        f"CAST({clock} AS date) AS {column}"
        for clock, column in zip(CLOCKS, DATE_COLUMNS, strict=True)
    )


def _source_ctes() -> str:
    normalized = ", ".join(
        column if index < 2 else f"nullif({column}, '') AS {column}"
        for index, column in enumerate(SOURCE_COLUMNS[:9])
    )
    clocks = ", ".join(
        f"CAST(CASE WHEN {_valid_timestamp(column)} THEN {column} END "
        f"AS timestamp without time zone) AS {column}"
        for column in CLOCKS
    )
    return (
        f"WITH raw_normalized AS MATERIALIZED (SELECT {normalized} FROM raw.order_reviews), "
        "raw_numeric AS MATERIALIZED (SELECT *, "
        f"CAST(CASE WHEN review_score ~ '{DECIMAL_PATTERN}' "
        "AND pg_input_is_valid(review_score, 'numeric') THEN review_score END AS numeric) "
        "AS score_number FROM raw_normalized), "
        "raw_typed AS MATERIALIZED (SELECT _load_id, _source_row, "
        'review_id COLLATE "C" AS review_id, order_id COLLATE "C" AS order_id, '
        f"CASE WHEN {_valid_score('score_number')} THEN CAST(score_number AS bigint) "
        "END AS review_score, "
        'review_comment_title COLLATE "C" AS review_comment_title, '
        'review_comment_message COLLATE "C" AS review_comment_message, '
        + clocks
        + " FROM raw_numeric), "
        "raw_source AS MATERIALIZED (SELECT *, "
        "COALESCE(review_answer_timestamp<review_creation_date, false) "
        "AS is_answer_before_creation FROM raw_typed), "
        f"raw_expected AS MATERIALIZED (SELECT *, {_date_fields()} FROM raw_source), "
        f"staged_source AS MATERIALIZED (SELECT {_fields(SOURCE_COLUMNS)} "
        "FROM staging.stg_order_reviews), "
        f"staged_expected AS MATERIALIZED (SELECT *, {_date_fields()} FROM staged_source), "
        f"actual AS MATERIALIZED (SELECT {_fields(COLUMNS)} FROM core.fact_reviews) "
    )


def _diagnostic(connection: psycopg.Connection, query: str, params=None):
    try:
        return connection.execute(query, params, binary=True)
    except psycopg.Error:
        pytest.fail(
            "Review-fact physical query failed; inspect private local configuration.", pytrace=False
        )


@pytest.fixture
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
            "Review-fact physical setup failed; inspect private local configuration.", pytrace=False
        )
    try:
        yield connection
    finally:
        with suppress(Exception):
            stack.close()


def test_review_fact_restricted_session_types_collations_ownership_and_private_access(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
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
    assert _diagnostic(
        connection,
        "SELECT has_schema_privilege(current_user, 'raw', 'USAGE'), "
        "has_schema_privilege(current_user, 'raw', 'CREATE'), "
        "has_table_privilege(current_user, 'raw.order_reviews', 'SELECT'), "
        "has_table_privilege(current_user, 'raw.order_reviews', "
        "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'), "
        "has_schema_privilege(current_user, 'staging', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'USAGE'), "
        "has_schema_privilege(current_user, 'core', 'CREATE')",
    ).fetchone() == (True, False, True, False, True, True, True)
    assert _diagnostic(
        connection,
        "SELECT c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname='fact_reviews'",
    ).fetchone() == ("v", "commercelens_transformer")
    assert _diagnostic(
        connection,
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
        "WHERE a.attrelid='core.fact_reviews'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
    ).fetchall() == list(zip(COLUMNS, TYPES, strict=True))
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(a.atttypid=s.atttypid AND a.atttypmod=s.atttypmod "
        "AND a.attcollation=s.attcollation) FROM pg_attribute a JOIN pg_attribute s "
        "ON s.attrelid='staging.stg_order_reviews'::regclass AND s.attname=a.attname "
        "AND s.attnum>0 AND NOT s.attisdropped WHERE a.attrelid='core.fact_reviews'::regclass "
        "AND a.attnum>0 AND NOT a.attisdropped",
    ).fetchone() == (10, True)
    assert _diagnostic(
        connection,
        "SELECT count(*), bool_and(NOT has_schema_privilege(rolname, 'core', 'USAGE,CREATE') "
        "AND NOT has_table_privilege(rolname, 'core.fact_reviews', "
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')) "
        "FROM pg_roles WHERE rolname IN "
        "('anon','authenticated','service_role','commercelens_reader')",
    ).fetchone() == (4, True)
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='core' AND c.relname IN "
        "('fact_reviews__dbt_tmp','fact_reviews__dbt_backup')",
    ).fetchone() == (0,)


def test_review_fact_independent_raw_multisets_optional_text_reversals_dates_and_order_membership(
    transformer_connection: psycopg.Connection,
) -> None:
    connection = transformer_connection
    differences = []
    for left, right in (
        ("raw_source", "staged_source"),
        ("raw_expected", "staged_expected"),
        ("staged_expected", "actual"),
        ("raw_expected", "actual"),
    ):
        for expected, observed in ((left, right), (right, left)):
            differences.append(
                f"(SELECT count(*) FROM (SELECT * FROM {expected} EXCEPT ALL "
                f"SELECT * FROM {observed}) differences)"
            )
    rejected = " OR ".join(
        f"({column} IS NOT NULL AND NOT {_valid_timestamp(column)})" for column in CLOCKS
    )
    rejected += f" OR (review_score IS NOT NULL AND NOT {_valid_score('score_number')})"
    differences.append(f"(SELECT count(*) FROM raw_numeric WHERE {rejected})")
    assert (
        _diagnostic(connection, _source_ctes() + "SELECT " + ", ".join(differences)).fetchone()
        == (0,) * 9
    )
    summaries = " UNION ALL ".join(
        f"SELECT count(*), (SELECT count(*) FROM (SELECT review_id, order_id FROM {relation} "
        "GROUP BY review_id, order_id) pairs), "
        "count(*) FILTER (WHERE review_comment_title IS NULL), "
        "count(*) FILTER (WHERE review_comment_message IS NULL), "
        "count(*) FILTER (WHERE is_answer_before_creation), "
        f"(SELECT count(*) FROM (SELECT order_id FROM {relation} GROUP BY order_id "
        f"HAVING count(*)>1) multiple_review_orders) FROM {relation}"
        for relation in ("raw_source", "staged_source", "actual")
    )
    assert (
        _diagnostic(connection, _source_ctes() + summaries).fetchall()
        == [(99224, 99224, 87656, 58247, 0, 547)] * 3
    )
    date_checks = " OR ".join(
        f"{role} IS DISTINCT FROM CAST({clock} AS date)"
        for clock, role in zip(CLOCKS, DATE_COLUMNS, strict=True)
    )
    bounds = " OR ".join(
        f"({clock} NOT BETWEEN timestamp '{LOWER}' AND timestamp '{UPPER}' "
        f"OR {clock} IS DISTINCT FROM date_trunc('second', {clock}))"
        for clock in CLOCKS
    )
    assert _diagnostic(
        connection,
        "SELECT count(*) FROM core.fact_reviews WHERE "
        + " OR ".join(column + " IS NULL" for column in REQUIRED)
        + " OR review_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR order_id COLLATE \"C\" !~ '^[0-9a-f]{32}$' "
        "OR _source_row<1 OR review_score NOT BETWEEN 1 AND 5 "
        "OR is_answer_before_creation IS DISTINCT FROM "
        "COALESCE(review_answer_timestamp<review_creation_date, false) OR "
        + date_checks
        + " OR "
        + bounds,
    ).fetchone() == (0,)
    assert _diagnostic(
        connection,
        "WITH reviews AS MATERIALIZED (SELECT order_id, review_creation_calendar_date, "
        "review_answer_calendar_date FROM core.fact_reviews), required_dates AS ("
        "SELECT review_creation_calendar_date AS calendar_date FROM reviews "
        "WHERE review_creation_calendar_date IS NOT NULL UNION "
        "SELECT review_answer_calendar_date FROM reviews "
        "WHERE review_answer_calendar_date IS NOT NULL) "
        "SELECT (SELECT count(*) FROM reviews r WHERE NOT EXISTS ("
        'SELECT 1 FROM core.fact_orders o WHERE r.order_id COLLATE "C"=o.order_id COLLATE "C")), '
        "(SELECT count(*) FROM required_dates r WHERE NOT EXISTS ("
        "SELECT 1 FROM core.dim_date d WHERE r.calendar_date=d.calendar_date))",
    ).fetchone() == (0, 0)
