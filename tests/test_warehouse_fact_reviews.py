"""Execute actual review-fact SQL using query-only synthetic SQLite CTEs.

Configured generics render installed dbt macros. The date adapter covers only
canonical naive whole-second fixture timestamps; it does not establish native
timestamp/date types, source parsing, timezone independence or native SQL proof.
Regex and occurrence-aware EXCEPT ALL have bounded SQLite adapters. PostgreSQL
remains authoritative for physical types, casts and native multiset semantics.
No private configuration, network, datasets or persistent fixture tables are used.
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
CALENDARS = ("review_creation_calendar_date", "review_answer_calendar_date")
COLUMNS = (*SOURCE_COLUMNS, *CALENDARS)
COMMENTS = ("review_comment_title", "review_comment_message")
REQUIRED = tuple(column for column in COLUMNS if column not in COMMENTS)
SINGULARS = (
    "fact_reviews_grain",
    "fact_reviews_domains",
    "fact_reviews_source_reconciliation",
    "fact_reviews_relationships",
)
REVIEWS = (
    (
        LOAD,
        1,
        "a" * 32,
        "c" * 32,
        5,
        " Ótimo 🚀\nO'Brien <b>title</b> ",
        "first\nsecond\tline 'quoted' <script>alert('x')</script>",
        "2020-02-29 23:59:59",
        "2020-03-01 00:00:00",
        False,
    ),
    (
        OTHER_LOAD,
        1,
        "a" * 32,
        "d" * 32,
        1,
        None,
        " \t\n ",
        "2021-01-01 12:34:56",
        "2020-12-31 23:59:59",
        True,
    ),
    (
        LOAD,
        2,
        "b" * 32,
        "c" * 32,
        3,
        " \t ",
        None,
        "2019-12-30 00:00:00",
        "2019-12-30 00:00:00",
        False,
    ),
    (
        OTHER_LOAD,
        2,
        "e" * 32,
        "f" * 32,
        4,
        None,
        None,
        "2020-03-01 05:06:07",
        "2020-03-01 05:06:08",
        False,
    ),
)
EXPECTED = (
    (*REVIEWS[0], "2020-02-29", "2020-03-01"),
    (*REVIEWS[1], "2021-01-01", "2020-12-31"),
    (*REVIEWS[2], "2019-12-30", "2019-12-30"),
    (*REVIEWS[3], "2020-03-01", "2020-03-01"),
)
ORDERS = (("c" * 32,), ("d" * 32,), ("f" * 32,))
DATES = (
    ("2020-02-29",),
    ("2020-03-01",),
    ("2021-01-01",),
    ("2020-12-31",),
    ("2019-12-30",),
)
SUBSTITUTIONS = {
    "_load_id": "'33333333-3333-4333-8333-333333333333'",
    "_source_row": "_source_row + 10",
    "review_id": "'ffffffffffffffffffffffffffffffff'",
    "order_id": "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'",
    "review_score": "review_score + 1",
    "review_comment_title": "'changed title'",
    "review_comment_message": "'changed message'",
    "review_creation_date": "'2001-01-01 01:02:03'",
    "review_answer_timestamp": "'2001-01-01 01:02:03'",
    "is_answer_before_creation": "not is_answer_before_creation",
    "review_creation_calendar_date": "'2001-01-01'",
    "review_answer_calendar_date": "'2001-01-01'",
}
DUPLICATE_OUTPUT = (
    " union all select * from model_output where review_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
    " and order_id = 'dddddddddddddddddddddddddddddddd'"
)
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join("'ffffffffffffffffffffffffffffffff'" if c == "review_id" else c for c in COLUMNS)
    + " from model_output where review_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
    + " and order_id = 'dddddddddddddddddddddddddddddddd'"
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
        (PROJECT / "models/core/fact_reviews.yml").read_text("utf-8")
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
    return module.default__test_not_null(model="fact_reviews", column_name=column, **arguments)


def sqlite_statement(statement: str) -> str:
    statement = re.sub(
        r"cast\((review_creation_date|review_answer_timestamp) as date\)",
        lambda match: "date(" + match[1] + ")",
        statement,
        flags=re.IGNORECASE,
    ).replace(" !~ ", " not regexp ")

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
    reviews: tuple[tuple[object, ...], ...] = REVIEWS,
    orders: tuple[tuple[object, ...], ...] = ORDERS,
    dates: tuple[tuple[object, ...], ...] = DATES,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_order_reviews", SOURCE_COLUMNS, reviews),
        ("fact_orders", ("order_id",), orders),
        ("dim_date", ("calendar_date",), dates),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("model_output as (" + render("models/core/fact_reviews.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"fact_reviews as (select {fields} from model_output where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(generic)
        if generic
        else "select * from fact_reviews"
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


def test_pair_grain_retains_repeated_individual_ids_literal_comments_events_and_lineage() -> None:
    assert Counter(run_sql()) == Counter(EXPECTED)
    for singular in SINGULARS:
        assert run_sql(singular) == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
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
    ]
    assert sum(len(item.get("data_tests", [])) for item in contract()["columns"]) == 10
    assert all(
        not item.get("data_tests") for item in contract()["columns"] if item["name"] in COMMENTS
    )
    for column in REQUIRED:
        assert run_sql(generic=column) == []


@pytest.mark.parametrize("column", REQUIRED)
def test_required_null_input_is_retained_or_null_calendar_output_blocks_acceptance(
    column: str,
) -> None:
    if column in SOURCE_COLUMNS:
        row = list(REVIEWS[0])
        row[SOURCE_COLUMNS.index(column)] = None
        creation = None if column == "review_creation_date" else "2020-02-29"
        answer = None if column == "review_answer_timestamp" else "2020-03-01"
        inputs = {"reviews": (tuple(row),)}
        assert run_sql(**inputs) == [(*row, creation, answer)]
        assert run_sql(generic=column, **inputs) == [(None,)]
        assert run_sql("fact_reviews_domains", **inputs) == [(1,)]
        assert run_sql("fact_reviews_source_reconciliation", **inputs) == []
        if column in ("review_creation_date", "review_answer_timestamp"):
            role = CALENDARS[0 if column == "review_creation_date" else 1]
            assert run_sql(generic=role, **inputs) == [(None,)]
            assert run_sql("fact_reviews_relationships", **inputs) == []
    else:
        changes = {column: "null"}
        assert run_sql(generic=column, changes=changes) == [(None,)] * 4
        assert run_sql("fact_reviews_domains", changes=changes) == [(4,)]
        assert run_sql("fact_reviews_source_reconciliation", changes=changes) == [(4, 4, 4, 4)]


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_each_source_comment_lineage_warning_or_calendar_change_fails_full_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("fact_reviews_source_reconciliation", changes={column: expression}) == [
        (4, 4, 4, 4)
    ]


@pytest.mark.parametrize(
    "creation,answer,warning,creation_day,answer_day",
    [
        ("2020-02-29 23:59:59", "2020-03-01 00:00:00", False, "2020-02-29", "2020-03-01"),
        ("2000-02-29 00:00:00", "2000-02-29 00:00:00", False, "2000-02-29", "2000-02-29"),
        ("2021-01-01 00:00:00", "2020-12-31 23:59:59", True, "2021-01-01", "2020-12-31"),
        ("1677-09-21 00:12:44", "2262-04-11 23:47:16", False, "1677-09-21", "2262-04-11"),
        ("2262-04-11 23:47:16", "1677-09-21 00:12:44", True, "2262-04-11", "1677-09-21"),
    ],
)
def test_direct_date_roles_preserve_equal_reversed_leap_and_range_endpoint_events(
    creation: str, answer: str, warning: bool, creation_day: str, answer_day: str
) -> None:
    row = (*REVIEWS[0][:7], creation, answer, warning)
    inputs = {"reviews": (row,), "dates": ((creation_day,), (answer_day,))}
    assert run_sql(**inputs) == [(*row, creation_day, answer_day)]
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []


@pytest.mark.parametrize("column", ["review_id", "order_id"])
@pytest.mark.parametrize("key", ["A" * 32, "a" * 31, "１" * 32, "a" * 32 + " "])
def test_invalid_literal_source_key_is_preserved_and_blocks_ascii_hex_domain(
    column: str, key: str
) -> None:
    row = list(REVIEWS[0])
    row[SOURCE_COLUMNS.index(column)] = key
    inputs = {"reviews": (tuple(row),)}
    assert run_sql(**inputs) == [(*row, "2020-02-29", "2020-03-01")]
    assert run_sql("fact_reviews_domains", **inputs) == [(1,)]
    assert run_sql("fact_reviews_source_reconciliation", **inputs) == []


@pytest.mark.parametrize("expression", ["0", "-1"])
def test_source_ordinal_must_remain_positive(expression: str) -> None:
    assert run_sql("fact_reviews_domains", changes={"_source_row": expression}) == [(4,)]


@pytest.mark.parametrize("expression", ["0", "6"])
def test_score_domain_rejects_values_outside_one_through_five(expression: str) -> None:
    assert run_sql("fact_reviews_domains", changes={"review_score": expression}) == [(4,)]


def test_source_reversal_warning_must_match_retained_events_without_repair() -> None:
    assert run_sql(
        "fact_reviews_domains",
        changes={"is_answer_before_creation": "not is_answer_before_creation"},
    ) == [(4,)]


@pytest.mark.parametrize("column", CALENDARS)
def test_changed_nonnull_calendar_role_fails_timestamp_correspondence(column: str) -> None:
    assert run_sql("fact_reviews_domains", changes={column: "'2001-01-01'"}) == [(4,)]


@pytest.mark.parametrize(
    "orders,missing",
    [
        ((), 4),
        (ORDERS[:1], 2),
        ((("C" * 32,), *ORDERS[1:]), 2),
        ((("c" * 32 + " ",), *ORDERS[1:]), 2),
    ],
)
def test_missing_or_nonliteral_order_reference_fails_without_filtering_reviews(
    orders: tuple, missing: int
) -> None:
    assert Counter(run_sql(orders=orders)) == Counter(EXPECTED)
    assert run_sql("fact_reviews_relationships", orders=orders) == [(missing, 0)]
    assert run_sql("fact_reviews_source_reconciliation", orders=orders) == []


@pytest.mark.parametrize("missing_day", ["2020-02-29", "2020-12-31", "2019-12-30"])
def test_missing_creation_answer_or_shared_date_fails_once_per_distinct_calendar_key(
    missing_day: str,
) -> None:
    dates = tuple(row for row in DATES if row[0] != missing_day)
    assert Counter(run_sql(dates=dates)) == Counter(EXPECTED)
    assert run_sql("fact_reviews_relationships", dates=dates) == [(0, 1)]


def test_all_missing_parents_report_review_count_and_distinct_date_count_without_filtering() -> (
    None
):
    assert Counter(run_sql(orders=(), dates=())) == Counter(EXPECTED)
    assert run_sql("fact_reviews_relationships", orders=(), dates=()) == [(4, 5)]


def test_duplicate_parent_orders_or_dates_do_not_fan_out_review_projection() -> None:
    inputs = {"orders": ORDERS * 2, "dates": DATES * 2}
    assert Counter(run_sql(**inputs)) == Counter(EXPECTED)
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []


@pytest.mark.parametrize("conflicting", [False, True])
def test_identical_or_conflicting_source_pair_duplicate_remains_visible_and_blocks_grain(
    conflicting: bool,
) -> None:
    duplicate = (
        (OTHER_LOAD, 100, *REVIEWS[0][2:5], "another title", *REVIEWS[0][6:])
        if conflicting
        else REVIEWS[0]
    )
    inputs = {"reviews": (*REVIEWS, duplicate)}
    assert Counter(run_sql(**inputs)) == Counter(
        (*EXPECTED, (*duplicate, "2020-02-29", "2020-03-01"))
    )
    assert run_sql("fact_reviews_grain", **inputs) == [(1,)]
    assert run_sql("fact_reviews_source_reconciliation", **inputs) == []


@pytest.mark.parametrize(
    "corruption,diagnostics",
    [
        (
            {
                "predicate": "not (review_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "
                "and order_id = 'dddddddddddddddddddddddddddddddd')"
            },
            (4, 3, 1, 0),
        ),
        ({"suffix": EXTRA_OUTPUT}, (4, 5, 0, 1)),
        ({"suffix": DUPLICATE_OUTPUT}, (4, 5, 0, 1)),
    ],
)
def test_omitted_warning_review_extra_or_duplicate_output_fails_full_conservation(
    corruption: dict, diagnostics: tuple
) -> None:
    assert run_sql("fact_reviews_source_reconciliation", **corruption) == [diagnostics]


def test_count_preserving_duplicate_replacement_fails_both_multiset_directions_and_grain() -> None:
    corruption = {
        "predicate": "not (review_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "
        "and order_id = 'cccccccccccccccccccccccccccccccc')",
        "suffix": DUPLICATE_OUTPUT,
    }
    assert len(run_sql(**corruption)) == len(REVIEWS)
    assert run_sql("fact_reviews_grain", **corruption) == [(1,)]
    assert run_sql("fact_reviews_source_reconciliation", **corruption) == [(4, 4, 1, 1)]


def test_empty_relations_produce_an_empty_valid_twelve_column_fact() -> None:
    inputs = {"reviews": (), "orders": (), "dates": ()}
    assert run_sql(**inputs) == []
    for singular in SINGULARS:
        assert run_sql(singular, **inputs) == []
    for column in REQUIRED:
        assert run_sql(generic=column, **inputs) == []
