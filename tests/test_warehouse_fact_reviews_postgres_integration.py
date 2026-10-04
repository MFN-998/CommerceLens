"""Opt-in native review-fact checks with bounded read-only typed CTEs.

Actual SQL, singular checks and configured dbt macros retain every review/order
pair and literal optional comment. Python naive datetime.date supplies the
independent calendar-role oracle. No warehouse rows or objects are changed.
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
    os.getenv("COMMERCE_WAREHOUSE_FACT_REVIEWS_INTEGRATION") != "1",
    reason="Native read-only review-fact SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
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
SOURCE_TYPES = (
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
)
TYPES = (*SOURCE_TYPES, "date", "date")
TYPE_CODES = (2950, 20, 25, 25, 20, 25, 25, 1114, 1114, 16, 1082, 1082)
REQUIRED = tuple(column for column in COLUMNS if column not in SOURCE_COLUMNS[5:7])
SINGULARS = (
    "fact_reviews_grain",
    "fact_reviews_domains",
    "fact_reviews_source_reconciliation",
    "fact_reviews_relationships",
)
LOAD_A = UUID("11111111-1111-4111-8111-111111111111")
LOAD_B = UUID("22222222-2222-4222-8222-222222222222")
TARGET_ID = "a" * 32
TARGET_ORDER = "b" * 32
ORDER_IDS = (TARGET_ORDER, "c" * 32, "e" * 32, "f" * 32)
# The synthetic empty title proves this core projection does not normalize text.
# Accepted raw-to-staging parsing normally converts exact empty text to NULL.
REVIEWS = (
    (
        LOAD_A,
        4294967297,
        TARGET_ID,
        TARGET_ORDER,
        5,
        " São Paulo ",
        "<b>literal & 'quoted'</b>\n𐍈🙂",
        datetime(2018, 1, 1),
        datetime(2018, 1, 2, 23, 59, 59),
        False,
    ),
    (
        LOAD_A,
        2,
        TARGET_ID,
        ORDER_IDS[1],
        1,
        None,
        " \t\n",
        datetime(2018, 1, 2),
        datetime(2018, 1, 1, 23, 59, 59),
        True,
    ),
    (
        LOAD_A,
        3,
        "d" * 32,
        TARGET_ORDER,
        3,
        "",
        "café CAFÉ\r\n新しい",
        datetime(2018, 1, 1, 23, 59, 59),
        datetime(2018, 1, 2),
        False,
    ),
    (
        LOAD_B,
        1,
        "e" * 32,
        ORDER_IDS[1],
        4,
        "\t whitespace\n",
        None,
        datetime(2016, 2, 29, 23, 59, 59),
        datetime(2016, 3, 1),
        False,
    ),
    (
        LOAD_B,
        2,
        "f" * 32,
        ORDER_IDS[2],
        2,
        "Case",
        "case",
        datetime(2017, 12, 31, 23, 59, 59),
        datetime(2018, 1, 1),
        False,
    ),
    (
        LOAD_B,
        3,
        "0" * 32,
        ORDER_IDS[3],
        5,
        "unchanged",
        "長" * 4096,
        datetime(2020, 4, 9, 23, 59, 59),
        datetime(2020, 4, 9, 23, 59, 59),
        False,
    ),
)
DATES = tuple(sorted({clock.date() for row in REVIEWS for clock in row[7:9]}))


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _reference(name: str) -> str:
    return {
        "stg_order_reviews": "synthetic_reviews",
        "fact_orders": "synthetic_orders",
        "dim_date": "synthetic_dates",
        "fact_reviews": "synthetic_projection",
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


def _generic_sql(column: str) -> str:
    yaml = pytest.importorskip("yaml")
    model = yaml.safe_load((PROJECT / "models/core/fact_reviews.yml").read_text("utf-8"))["models"][
        0
    ]
    assert model["name"] == "fact_reviews"
    assert model["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in model["columns"]) == COLUMNS
    assert tuple(item["data_type"] for item in model["columns"]) == TYPES
    assert tuple(item["name"] for item in model["columns"] if item.get("data_tests")) == REQUIRED
    assert all(
        item.get("data_tests", []) == (["not_null"] if item["name"] in REQUIRED else [])
        for item in model["columns"]
    )
    assert column in REQUIRED
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql/not_null.sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return module.default__test_not_null(model="synthetic_projection", column_name=column).strip()


def _changed(column: str, replacement: object):
    row = list(REVIEWS[0])
    row[SOURCE_COLUMNS.index(column)] = replacement
    return (tuple(row), *REVIEWS[1:])


def _expected(reviews=REVIEWS) -> Counter:
    return Counter(
        (*row, *(clock.date() if clock is not None else None for clock in row[7:9]))
        for row in reviews
    )


def _cte(
    *,
    reviews=REVIEWS,
    orders=ORDER_IDS,
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
        ("reviews", SOURCE_COLUMNS, SOURCE_TYPES, reviews),
        ("orders", ("order_id",), ("text",), tuple((value,) for value in orders)),
        ("dates", ("calendar_date",), ("date",), tuple((value,) for value in dates)),
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
    ctes.append("synthetic_actual as (" + _render("models/core/fact_reviews.sql") + ")")
    fields = []
    target = (
        'review_id COLLATE "C"=%s::text COLLATE "C" and order_id COLLATE "C"=%s::text COLLATE "C"'
    )
    for column, kind in zip(COLUMNS, TYPES, strict=True):
        if override is not None and column == override[0]:
            fields.append(
                "case when "
                + target
                + " then %s::"
                + kind
                + " else "
                + column
                + " end as "
                + column
            )
            parameters.extend((TARGET_ID, TARGET_ORDER, override[1]))
        else:
            fields.append(column)
    selection = "select " + ", ".join(fields) + " from synthetic_actual"
    if mode == "missing":
        selection += " where not (" + target + ")"
        parameters.extend((TARGET_ID, TARGET_ORDER))
    elif mode in {"extra", "duplicate"}:
        added = [
            "%s::text" if mode == "extra" and column == "review_id" else column
            for column in COLUMNS
        ]
        selection += (
            " union all select " + ", ".join(added) + " from synthetic_actual where " + target
        )
        if mode == "extra":
            parameters.append("9" * 32)
        parameters.extend((TARGET_ID, TARGET_ORDER))
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
            "Review-fact native setup failed; inspect private local configuration.", pytrace=False
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
            "Review-fact native query failed; inspect private local configuration.", pytrace=False
        )


def _singular(connection: psycopg.Connection, name: str, **options: object):
    assert name in SINGULARS
    return _query(
        connection,
        "select * from (" + _render("tests/" + name + ".sql") + ") diagnostics",
        **options,
    ).fetchall()


def _null_counts(connection: psycopg.Connection, **options: object):
    checks = [
        "(select count(*) from (" + _generic_sql(column) + ") failures)" for column in REQUIRED
    ]
    result = _query(connection, "select " + ", ".join(checks), **options).fetchone()
    return dict(zip(REQUIRED, result, strict=True))


def _assert_shape(result) -> None:
    assert result.description is not None
    assert tuple(column.name for column in result.description) == COLUMNS
    assert tuple(column.type_code for column in result.description) == TYPE_CODES


@pytest.mark.parametrize("source_collation", [None, "POSIX"])
@pytest.mark.parametrize("timezone", ["UTC", "Pacific/Honolulu"])
def test_projection_keeps_repeated_ids_literal_comments_reversal_and_naive_dates(
    transformer_connection: psycopg.Connection, source_collation: str | None, timezone: str
) -> None:
    assert timezone in {"UTC", "Pacific/Honolulu"}
    transformer_connection.execute("SET LOCAL TIME ZONE '" + timezone + "'")
    options = {"source_collation": source_collation}
    result = _query(transformer_connection, "select * from synthetic_actual", **options)
    _assert_shape(result)
    assert Counter(result.fetchall()) == _expected()
    equality = " AND ".join(
        f"pg_collation_for(a.{column}) IS NOT DISTINCT FROM pg_collation_for(s.{column})"
        for column in ("review_id", "order_id", "review_comment_title", "review_comment_message")
    )
    assert _query(
        transformer_connection,
        "select bool_and(" + equality + ") from synthetic_actual a join synthetic_reviews s "
        'on a.review_id COLLATE "C"=s.review_id COLLATE "C" '
        'and a.order_id COLLATE "C"=s.order_id COLLATE "C"',
        **options,
    ).fetchone() == (True,)
    assert _null_counts(transformer_connection, **options) == dict.fromkeys(REQUIRED, 0)
    for name in SINGULARS:
        assert _singular(transformer_connection, name, **options) == []


@pytest.mark.parametrize("column", REQUIRED)
def test_required_null_remains_visible_and_actual_yaml_macro_blocks_it(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    options = (
        {"reviews": _changed(column, None)}
        if column in SOURCE_COLUMNS
        else {"override": (column, None)}
    )
    assert _null_counts(transformer_connection, **options)[column] == 1
    if column in SOURCE_COLUMNS:
        assert Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        ) == _expected(options["reviews"])
        assert (
            _singular(transformer_connection, "fact_reviews_source_reconciliation", **options) == []
        )
    assert _singular(transformer_connection, "fact_reviews_domains", **options) == [(1,)]


def test_true_duplicate_pair_is_retained_and_blocks_grain_without_individual_id_uniqueness(
    transformer_connection: psycopg.Connection,
) -> None:
    reviews = (*REVIEWS, (LOAD_B, 4, *REVIEWS[0][2:]))
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", reviews=reviews).fetchall()
    ) == _expected(reviews)
    assert _singular(transformer_connection, "fact_reviews_grain", reviews=reviews) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_reviews_source_reconciliation", reviews=reviews)
        == []
    )


MUTATIONS = (
    LOAD_B,
    1,
    "9" * 32,
    ORDER_IDS[2],
    1,
    "São Paulo",
    "changed <b>comment</b>",
    datetime(2018, 1, 3),
    datetime(2018, 1, 4),
    True,
    date(2018, 1, 3),
    date(2018, 1, 4),
)


@pytest.mark.parametrize("column,replacement", list(zip(COLUMNS, MUTATIONS, strict=True)))
def test_complete_twelve_field_reconciliation_blocks_each_count_preserving_change(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _singular(
        transformer_connection, "fact_reviews_source_reconciliation", override=(column, replacement)
    ) == [(6, 6, 1, 1)]


@pytest.mark.parametrize(
    "mode,diagnostics",
    [("missing", (6, 5, 1, 0)), ("extra", (6, 7, 0, 1)), ("duplicate", (6, 7, 0, 1))],
)
def test_complete_multiset_blocks_missing_extra_and_duplicate_output(
    transformer_connection: psycopg.Connection, mode: str, diagnostics: tuple[int, ...]
) -> None:
    assert _singular(transformer_connection, "fact_reviews_source_reconciliation", mode=mode) == [
        diagnostics
    ]
    if mode == "duplicate":
        assert _singular(transformer_connection, "fact_reviews_grain", mode=mode) == [(1,)]


@pytest.mark.parametrize(
    "column,replacement",
    [
        ("review_id", "A" * 32),
        ("review_id", " " + TARGET_ID),
        ("review_id", "ａ" * 32),
        ("order_id", "B" * 32),
        ("order_id", " " + TARGET_ORDER),
        ("order_id", "ｂ" * 32),
        ("_source_row", 0),
        ("review_score", 0),
        ("review_score", 6),
        ("is_answer_before_creation", True),
    ],
)
def test_invalid_source_domains_or_warning_correspondence_are_retained_and_blocked(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    reviews = _changed(column, replacement)
    assert Counter(
        _query(transformer_connection, "select * from synthetic_actual", reviews=reviews).fetchall()
    ) == _expected(reviews)
    assert _singular(transformer_connection, "fact_reviews_domains", reviews=reviews) == [(1,)]
    assert (
        _singular(transformer_connection, "fact_reviews_source_reconciliation", reviews=reviews)
        == []
    )


@pytest.mark.parametrize(
    "orders",
    [
        ORDER_IDS[1:],
        (TARGET_ORDER.upper(), *ORDER_IDS[1:]),
        (" " + TARGET_ORDER + " ", *ORDER_IDS[1:]),
        ("ｂ" * 32, *ORDER_IDS[1:]),
    ],
)
def test_missing_literal_order_reference_blocks_without_review_selection_or_pair_loss(
    transformer_connection: psycopg.Connection, orders: tuple[str, ...]
) -> None:
    assert (
        Counter(
            _query(
                transformer_connection, "select * from synthetic_actual", orders=orders
            ).fetchall()
        )
        == _expected()
    )
    assert _singular(transformer_connection, "fact_reviews_relationships", orders=orders) == [
        (2, 0)
    ]
    assert (
        _singular(transformer_connection, "fact_reviews_source_reconciliation", orders=orders) == []
    )


@pytest.mark.parametrize("column", DATE_COLUMNS)
@pytest.mark.parametrize("replacement", [None, date(2030, 1, 1)])
def test_each_calendar_role_mismatch_blocks_correspondence_and_nonnull_membership(
    transformer_connection: psycopg.Connection, column: str, replacement: date | None
) -> None:
    options = {"override": (column, replacement)}
    assert _singular(transformer_connection, "fact_reviews_domains", **options) == [(1,)]
    assert _singular(transformer_connection, "fact_reviews_source_reconciliation", **options) == [
        (6, 6, 1, 1)
    ]
    assert _singular(transformer_connection, "fact_reviews_relationships", **options) == (
        [] if replacement is None else [(0, 1)]
    )


@pytest.mark.parametrize("column", DATE_COLUMNS)
def test_each_recorded_date_role_requires_parent_without_filtering_or_repair(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    required_date = REVIEWS[0][7 + DATE_COLUMNS.index(column)].date()
    dates = tuple(value for value in DATES if value != required_date)
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", dates=dates).fetchall()
        )
        == _expected()
    )
    assert _singular(transformer_connection, "fact_reviews_relationships", dates=dates) == [(0, 1)]


def test_duplicate_parent_keys_cannot_multiply_review_pairs_or_select_comments(
    transformer_connection: psycopg.Connection,
) -> None:
    options = {"orders": (*ORDER_IDS, TARGET_ORDER), "dates": (*DATES, DATES[0])}
    assert (
        Counter(
            _query(transformer_connection, "select * from synthetic_actual", **options).fetchall()
        )
        == _expected()
    )
    for name in SINGULARS:
        assert _singular(transformer_connection, name, **options) == []


def test_empty_and_all_null_sources_keep_twelve_typed_fields_without_losing_records(
    transformer_connection: psycopg.Connection,
) -> None:
    empty = _query(
        transformer_connection, "select * from synthetic_actual", reviews=(), orders=(), dates=()
    )
    _assert_shape(empty)
    assert empty.fetchall() == []
    assert _null_counts(transformer_connection, reviews=(), orders=(), dates=()) == dict.fromkeys(
        REQUIRED, 0
    )
    for name in SINGULARS:
        assert _singular(transformer_connection, name, reviews=(), orders=(), dates=()) == []
    reviews = ((None,) * len(SOURCE_COLUMNS),)
    result = _query(transformer_connection, "select * from synthetic_actual", reviews=reviews)
    _assert_shape(result)
    assert result.fetchall() == [(None,) * len(COLUMNS)]
    assert _null_counts(transformer_connection, reviews=reviews) == dict.fromkeys(REQUIRED, 1)
    assert _singular(transformer_connection, "fact_reviews_domains", reviews=reviews) == [(1,)]
    assert _singular(transformer_connection, "fact_reviews_relationships", reviews=reviews) == [
        (1, 0)
    ]
    assert (
        _singular(transformer_connection, "fact_reviews_source_reconciliation", reviews=reviews)
        == []
    )
