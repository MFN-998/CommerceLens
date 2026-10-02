"""Execute actual review projection, singular and dbt generic SQL offline.

Bound synthetic VALUES stay in query-only in-memory SQLite. Regex, calendar and
timestamp casts use adapter shims; EXCEPT ALL uses equivalent row-numbered
NULL-safe multiset subtraction. SQLite numeric examples are small: PostgreSQL
physical types, exact bigint limits and planner behavior require native acceptance.
This suite focuses review/order pairs, literal optional text, score and reversals.
No fixture files or persistent database resources are created or removed.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
COLUMNS = (
    "_load_id",
    "_source_row",
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
)
COMMENTS = COLUMNS[5:7]
DATES = COLUMNS[7:]
MANDATORY = COLUMNS[:5] + DATES
FLAG = "is_answer_before_creation"
EXPECTED_COLUMNS = (*COLUMNS, FLAG)
LOAD = "11111111-1111-4111-8111-111111111111"
REVIEW = "a" * 32
ORDER = "b" * 32


def review(**changes: object) -> tuple[object, ...]:
    values: dict[str, object] = dict(
        zip(
            COLUMNS,
            (
                LOAD,
                1,
                REVIEW,
                ORDER,
                "5",
                "Ótimo",
                "Entrega rápida!",
                "2018-01-01 00:00:00",
                "2018-01-02 03:04:05",
            ),
            strict=True,
        )
    )
    assert set(changes) <= set(values)
    values.update(changes)
    return tuple(values[column] for column in COLUMNS)


def render_sql(relative_path: str) -> str:
    jinja2 = pytest.importorskip("jinja2")
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    macros = "\n".join(
        (PROJECT / "macros" / name).read_text("utf-8")
        for name in ("source_numeric.sql", "source_timestamp.sql")
    )

    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_reviews")
        return "synthetic_order_reviews"

    def ref(name: str) -> str:
        assert name == "stg_order_reviews"
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
    return yaml.safe_load((PROJECT / "models/staging/stg_order_reviews.yml").read_text("utf-8"))[
        "models"
    ][0]


def render_generic(column: str, name: str) -> str:
    """Render installed dbt generic SQL using the actual review YAML contract."""
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
    """Small-value adapter; native PostgreSQL remains the type/calendar authority."""
    if value is None:
        return None
    try:
        if type_name == "timestamp without time zone":
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return 1
        assert type_name == "numeric"
        number = Decimal(value)
        return int(number.is_finite() and (-16383 <= number.adjusted() <= 131071 or number == 0))
    except (InvalidOperation, ValueError, OverflowError):
        return 0


def sqlite_except_all(statement: str) -> str:
    """Adapter equivalent for duplicate-preserving multiset subtraction."""

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
    """Execute actual model/test SQL with bound inputs and optional staged damage."""
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
        "with synthetic_order_reviews ("
        + ", ".join(COLUMNS)
        + ") as (values "
        + placeholders
        + "), synthetic_orders (order_id) as (values (?)), projected as ("
        + render_sql("models/staging/stg_order_reviews.sql")
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
    statement = re.sub(
        r"cast\((case(?:(?!\bcast\s*\().)*?end) as timestamp without time zone\)",
        r"timestamp_cast(\1)",
        statement,
        flags=re.DOTALL,
    )
    statement = sqlite_except_all(statement)
    connection = sqlite3.connect(":memory:")
    try:
        connection.create_function("pg_input_is_valid", 2, sqlite_input_valid)
        connection.create_function("timestamp_cast", 1, lambda value: value)
        connection.create_function("trunc", 1, lambda value: None if value is None else int(value))
        connection.create_collation("C", lambda left, right: (left > right) - (left < right))
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


def test_literal_source_fields_lineage_and_multiple_reviews_are_retained_without_parent_join() -> (
    None
):
    rows = [review(), review(_source_row=2, review_id="c" * 32, review_score="1")]
    projected = run_sql(rows, parent=None)
    assert len(projected) == 2
    for source, staged in zip(rows, projected, strict=True):
        assert staged[:4] == source[:4]
        assert staged[4] == int(source[4])
        assert staged[5:9] == source[5:9]
        assert staged[9] == 0
    assert run_sql(rows, "tests/stg_order_reviews_source_reconciliation.sql") == []


@pytest.mark.parametrize("column", COMMENTS)
@pytest.mark.parametrize(
    "text",
    [
        "  café d'água  ",
        " \t\n",
        "linha 1\nlinha 2\r\n",
        "😊 العربية",
        "<b>Excelente</b><script>alert('x')</script>",
    ],
)
def test_optional_text_preserves_unicode_whitespace_newlines_apostrophes_and_markup(
    column: str,
    text: str,
) -> None:
    source = review(**{column: text})
    assert run_sql([source])[0][COLUMNS.index(column)] == text
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []
    assert run_sql([source], "tests/stg_order_reviews_source_reconciliation.sql") == []


@pytest.mark.parametrize("column", COMMENTS)
@pytest.mark.parametrize("missing", ["", None])
def test_exact_empty_and_null_optional_comment_remain_valid_source_absence(
    column: str,
    missing: object,
) -> None:
    source = review(**{column: missing})
    assert run_sql([source])[0][COLUMNS.index(column)] is None
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []
    assert run_sql([source], "tests/stg_order_reviews_source_reconciliation.sql") == []


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_each_source_score_is_retained_and_actual_numeric_accepted_values_passes(
    score: int,
) -> None:
    source = review(review_score=str(score))
    assert run_sql([source])[0][4] == score
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []
    assert run_sql([source], generic=("review_score", "accepted_values")) == []


@pytest.mark.parametrize("text", ["5.0", "5e0", " \t+5.000\n"])
def test_score_uses_accepted_exact_integral_decimal_helper(text: str) -> None:
    source = review(review_score=text)
    assert run_sql([source])[0][4] == 5
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []


@pytest.mark.parametrize("score", [0, -1, 6])
def test_out_of_domain_integral_score_is_preserved_and_blocks_both_score_tests(score: int) -> None:
    source = review(review_score=str(score))
    assert run_sql([source])[0][4] == score
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=("review_score", "accepted_values")) == [(score, 1)]


@pytest.mark.parametrize("text", ["1.5", "bad", "NaN"])
def test_rejected_score_becomes_null_retains_row_and_blocks_without_rounding(text: str) -> None:
    source = review(review_score=text)
    assert run_sql([source])[0][4] is None
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=("review_score", "not_null")) == [(None,)]


@pytest.mark.parametrize("column", (*COLUMNS[2:5], *DATES))
@pytest.mark.parametrize("missing", ["", None])
def test_each_missing_mandatory_source_field_retains_row_and_blocks(
    column: str, missing: object
) -> None:
    source = review(**{column: missing})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    assert projected[9] == 0
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]
    assert run_sql([source], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("column", MANDATORY)
def test_actual_dbt_not_null_blocks_each_missing_source_or_lineage(column: str) -> None:
    assert run_sql([review(**{column: None})], generic=(column, "not_null")) == [(None,)]


@pytest.mark.parametrize("column", DATES)
@pytest.mark.parametrize("text", ["2018-02-29 03:04:05", "2018-1-1 1:2:3", "2018-01-01 03:04:05Z"])
def test_each_date_reuses_strict_source_parser_and_rejected_event_does_not_imply_reversal(
    column: str,
    text: str,
) -> None:
    source = review(**{column: text})
    projected = run_sql([source])[0]
    assert projected[COLUMNS.index(column)] is None
    assert projected[9] == 0
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]


@pytest.mark.parametrize(
    "creation,answer,flag",
    [
        ("2018-01-03 00:00:00", "2018-01-02 03:04:05", 1),
        ("2018-01-02 03:04:05", "2018-01-02 03:04:05", 0),
        ("2018-01-01 00:00:00", "2018-01-02 03:04:05", 0),
    ],
)
def test_reversed_equal_and_ordered_events_preserve_exact_dates_and_warning(
    creation: str,
    answer: str,
    flag: int,
) -> None:
    source = review(review_creation_date=creation, review_answer_timestamp=answer)
    assert run_sql([source])[0][7:] == (creation, answer, flag)
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []
    assert run_sql([source], "tests/stg_order_reviews_source_reconciliation.sql") == []


def test_reversal_flag_is_nonnull_and_actual_dbt_test_detects_null_mutation() -> None:
    assert run_sql([review()], generic=(FLAG, "not_null")) == []
    assert run_sql([review()], generic=(FLAG, "not_null"), changes={FLAG: "null"}) == [(None,)]


@pytest.mark.parametrize("column", ("review_id", "order_id"))
@pytest.mark.parametrize("text", ["A" * 32, "short", " " + "a" * 32])
def test_invalid_literal_ids_preserve_source_spelling_and_block(column: str, text: str) -> None:
    source = review(**{column: text})
    assert run_sql([source])[0][COLUMNS.index(column)] == text
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]


@pytest.mark.parametrize("ordinal", [None, 0, -1])
def test_missing_or_nonpositive_source_ordinal_blocks(ordinal: object) -> None:
    source = review(_source_row=ordinal)
    assert run_sql([source])[0][1] == ordinal
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]


def test_actual_order_relationship_fails_orphan_and_preserves_review_pair() -> None:
    source = review(order_id="c" * 32)
    assert run_sql([source])[0][3] == "c" * 32
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == []
    assert run_sql([source], generic=("order_id", "relationships")) == [("c" * 32,)]
    assert run_sql([review()], generic=("order_id", "relationships")) == []


def test_individual_review_and_order_ids_can_repeat_at_distinct_pair_grain() -> None:
    rows = [
        review(),
        review(_source_row=2, review_id="c" * 32),
        review(_source_row=3, order_id="d" * 32),
    ]
    assert len(run_sql(rows)) == 3
    assert run_sql(rows, "tests/stg_order_reviews_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_reviews_lineage_unique.sql") == []


def test_duplicate_review_order_pair_at_distinct_lineage_is_retained_and_blocks_grain() -> None:
    rows = [review(), review(_source_row=2, review_comment_message="another message")]
    assert len(run_sql(rows)) == 2
    assert run_sql(rows, "tests/stg_order_reviews_grain.sql") == [(1,)]
    assert run_sql(rows, "tests/stg_order_reviews_lineage_unique.sql") == []


def test_duplicate_lineage_at_distinct_review_pair_blocks_lineage_only() -> None:
    rows = [review(), review(review_id="c" * 32)]
    assert run_sql(rows, "tests/stg_order_reviews_grain.sql") == []
    assert run_sql(rows, "tests/stg_order_reviews_lineage_unique.sql") == [(1,)]


def test_source_ordinal_can_repeat_in_distinct_loads() -> None:
    rows = [review(), review(_load_id="22222222-2222-4222-8222-222222222222", review_id="c" * 32)]
    assert run_sql(rows, "tests/stg_order_reviews_lineage_unique.sql") == []


@pytest.mark.parametrize(
    "column,expression",
    [
        ("_load_id", "'22222222-2222-4222-8222-222222222222'"),
        ("_source_row", "_source_row+1"),
        ("review_id", "'" + "c" * 32 + "'"),
        ("order_id", "'" + "c" * 32 + "'"),
        ("review_score", "review_score-1"),
        ("review_comment_title", "'changed title'"),
        ("review_comment_message", "'changed message'"),
        ("review_creation_date", "'2018-01-02 00:00:00'"),
        ("review_answer_timestamp", "'2018-01-02 03:04:06'"),
        (FLAG, "true"),
    ],
)
def test_multiset_reconciliation_detects_each_source_lineage_or_flag_substitution(
    column: str,
    expression: str,
) -> None:
    assert run_sql(
        [review()],
        "tests/stg_order_reviews_source_reconciliation.sql",
        changes={column: expression},
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_distinguishes_optional_null_from_empty_text() -> None:
    source = review(review_comment_title="", review_comment_message=None)
    assert run_sql([source], "tests/stg_order_reviews_source_reconciliation.sql") == []
    assert run_sql(
        [source],
        "tests/stg_order_reviews_source_reconciliation.sql",
        changes={"review_comment_title": "''"},
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_dropped_or_extra_duplicate_review_pair() -> None:
    rows = [review(), review(_source_row=2, review_id="c" * 32)]
    assert run_sql(
        rows, "tests/stg_order_reviews_source_reconciliation.sql", staged_filter="_source_row<>1"
    ) == [("missing_from_staging", 1)]
    assert run_sql(
        rows,
        "tests/stg_order_reviews_source_reconciliation.sql",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("unexpected_in_staging", 1)]


def test_multiset_reconciliation_detects_same_count_duplicate_substitution() -> None:
    rows = [review(), review(_source_row=2, review_id="c" * 32)]
    assert run_sql(
        rows,
        "tests/stg_order_reviews_source_reconciliation.sql",
        staged_filter="_source_row=1",
        staged_suffix=" union all select * from projected where _source_row=1",
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


def test_rejected_mandatory_date_reconciles_as_null_while_domains_still_block() -> None:
    source = review(review_answer_timestamp="bad")
    assert run_sql([source])[0][9] == 0
    assert run_sql([source], "tests/stg_order_reviews_source_reconciliation.sql") == []
    assert run_sql([source], "tests/stg_order_reviews_source_domains.sql") == [(1,)]


def test_contract_declares_optional_text_types_numeric_score_and_fourteen_data_tests() -> None:
    contract = model_contract()
    assert contract["config"] == {"materialized": "view", "schema": "staging"}
    columns = contract["columns"]
    assert tuple(record["name"] for record in columns) == EXPECTED_COLUMNS
    assert tuple(record["data_type"] for record in columns) == (
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
    assert sum(len(record.get("data_tests", [])) for record in columns) + 4 == 14
    for record in columns:
        assert ("not_null" in record.get("data_tests", [])) == (record["name"] not in COMMENTS)
    score = next(record for record in columns if record["name"] == "review_score")
    assert score["data_tests"][1]["accepted_values"]["arguments"] == {
        "values": [1, 2, 3, 4, 5],
        "quote": False,
    }
