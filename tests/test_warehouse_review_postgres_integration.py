"""Native review SQL checks with bounded synthetic, read-only VALUES inputs.

Render the real model/macros, singular tests, and YAML-configured dbt generic SQL.
Independent literals verify source text, naive dates, score domains and reversals.
Native EXCEPT ALL detects text/boolean corruption and multiplicity changes. No
raw records, fixture tables, temporary relations, or warehouse writes are used.
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
    os.getenv("COMMERCE_WAREHOUSE_REVIEW_INTEGRATION") != "1",
    reason="Native read-only review SQL checks require explicit opt-in",
)

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = UUID("11111111-1111-4111-8111-111111111111")
OTHER_LOAD = UUID("22222222-2222-4222-8222-222222222222")
REVIEW_ID = "a" * 32
ORDER_ID = "b" * 32
OTHER_ORDER_ID = "c" * 32
SOURCE_COLUMNS = ("_load_id", "_source_row", *TABLES["order_reviews"].columns)
TEXT_COLUMNS = ("review_comment_title", "review_comment_message")
DATE_COLUMNS = ("review_creation_date", "review_answer_timestamp")
MANDATORY_SOURCE = tuple(
    name for name, column in TABLES["order_reviews"].columns.items() if not column.nullable
)
FLAG = "is_answer_before_creation"
EXPECTED_COLUMNS = (*SOURCE_COLUMNS, FLAG)
SCORE_CASES = (
    ("lowest-score", "1", 1, 0, 0),
    ("integral-decimal-score", "3.0", 3, 0, 0),
    ("highest-score", "5", 5, 0, 0),
    ("below-score-domain", "0", 0, 1, 1),
    ("above-score-domain", "6", 6, 1, 1),
    ("fractional-score", "4.5", None, 1, 0),
)
DATE_CASES = (
    (
        "answer-after-creation",
        "2018-01-02 03:04:05",
        "2018-01-03 03:04:05",
        datetime(2018, 1, 2, 3, 4, 5),
        datetime(2018, 1, 3, 3, 4, 5),
        False,
    ),
    (
        "genuine-reversal",
        "2018-01-03 03:04:05",
        "2018-01-02 03:04:05",
        datetime(2018, 1, 3, 3, 4, 5),
        datetime(2018, 1, 2, 3, 4, 5),
        True,
    ),
    (
        "equal-whole-second",
        "2018-01-02 03:04:05",
        "2018-01-02 03:04:05",
        datetime(2018, 1, 2, 3, 4, 5),
        datetime(2018, 1, 2, 3, 4, 5),
        False,
    ),
)


def _source_row(changes: dict[str, object] | None = None) -> tuple[object, ...]:
    fields: dict[str, object] = {
        "_load_id": LOAD,
        "_source_row": 1,
        "review_id": REVIEW_ID,
        "order_id": ORDER_ID,
        "review_score": "3",
        "review_comment_title": "Café d'Água",
        "review_comment_message": "Linha um\nLinha dois: ótimo!",
        "review_creation_date": "2018-01-02 03:04:05",
        "review_answer_timestamp": "2018-01-03 03:04:05",
    }
    fields.update(changes or {})
    return tuple(fields[column] for column in SOURCE_COLUMNS)


def _environment():
    jinja2 = pytest.importorskip("jinja2")
    return jinja2.Environment(undefined=jinja2.StrictUndefined)


def _render_sql(relative_path: str) -> str:
    def source(schema: str, table: str) -> str:
        assert (schema, table) == ("raw", "order_reviews")
        return "synthetic_reviews"

    def ref(model: str) -> str:
        assert model in {"stg_order_reviews", "stg_orders"}
        return "synthetic_projection" if model == "stg_order_reviews" else "synthetic_orders"

    def config(**options: object) -> str:
        assert options == {"severity": "error", "store_failures": False}
        return ""

    macros = "\n".join(
        (PROJECT / "macros" / filename).read_text("utf-8")
        for filename in ("source_numeric.sql", "source_timestamp.sql")
    )
    template = (PROJECT / relative_path).read_text("utf-8")
    return (
        _environment()
        .from_string(macros + "\n" + template)
        .render(source=source, ref=ref, config=config)
        .strip()
        .removesuffix(";")
    )


def _generic_test_sql(column_name: str, name: str) -> str:
    # Use arguments from the actual model YAML, including numeric quote:false.
    yaml = pytest.importorskip("yaml")
    contract = yaml.safe_load(
        (PROJECT / "models/staging/stg_order_reviews.yml").read_text("utf-8")
    )["models"][0]
    tests = next(column for column in contract["columns"] if column["name"] == column_name)[
        "data_tests"
    ]
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = definition[name]["arguments"].copy() if isinstance(definition, dict) else {}
    if name == "relationships":
        assert arguments["to"] == "ref('stg_orders')"
        arguments["to"] = "synthetic_orders"
    macro = (
        files("dbt")
        .joinpath("include/global_project/macros/generic_test_sql", name + ".sql")
        .read_text("utf-8")
    )
    module = _environment().from_string(macro).make_module({"should_store_failures": lambda: False})
    return getattr(module, "default__test_" + name)(
        model="synthetic_projection", column_name=column_name, **arguments
    ).strip()


def _synthetic_cte(
    rows: tuple[tuple[object, ...], ...],
    *,
    materialized: bool = True,
    duplicate_parents: bool = False,
    overrides: dict[str, object] | None = None,
    stage_mode: str = "same",
) -> tuple[str, tuple[object, ...]]:
    assert 1 <= len(rows) <= 4
    assert all(len(row) == len(SOURCE_COLUMNS) for row in rows)
    assert stage_mode in {"same", "distinct", "duplicate"}
    changes = overrides or {}
    assert set(changes) <= {*TEXT_COLUMNS, FLAG}
    assert not changes or stage_mode == "same"
    # MATERIALIZED mimics raw text columns. Inline mode probes custom-plan
    # folding of unreachable casts; explicit types preserve synthetic NULL shape.
    placeholders = ("%s::uuid", "%s::bigint", *("%s::text" for _ in SOURCE_COLUMNS[2:]))
    value_row = "(" + ", ".join(placeholders) + ")"
    materialization = "materialized " if materialized else ""
    orders = (ORDER_ID, OTHER_ORDER_ID) * (2 if duplicate_parents else 1)
    ctes = [
        "synthetic_reviews ("
        + ", ".join(SOURCE_COLUMNS)
        + ") as "
        + materialization
        + "(values "
        + ", ".join(value_row for _ in rows)
        + ")",
        "synthetic_orders (order_id) as materialized (values "
        + ", ".join("(%s::text)" for _ in orders)
        + ")",
        "synthetic_actual_projection as ("
        + _render_sql("models/staging/stg_order_reviews.sql")
        + ")",
    ]
    parameters = [*(value for row in rows for value in row), *orders]
    fields = []
    for column in EXPECTED_COLUMNS:
        if column in changes:
            type_name = "boolean" if column == FLAG else "text"
            fields.append("%s::" + type_name + " as " + column)
            parameters.append(changes[column])
        else:
            fields.append(column)
    selection = (
        "select "
        + ("distinct " if stage_mode == "distinct" else "")
        + ", ".join(fields)
        + " from synthetic_actual_projection"
    )
    if stage_mode == "duplicate":
        selection += " union all select * from synthetic_actual_projection"
    ctes.append("synthetic_projection as (" + selection + ")")
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
    """A failing case rolls back its savepoint without poisoning later cases."""
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
        cte + "select * from synthetic_projection order by _source_row, order_id, review_id",
        parameters,
    )
    assert result.description is not None
    names = tuple(column.name for column in result.description)
    assert names == EXPECTED_COLUMNS
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
        connection, (row,), "stg_order_reviews_source_domains.sql", "invalid_source_value_rows"
    )


def _generic_failures(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    column: str,
    name: str,
) -> int:
    cte, parameters = _synthetic_cte(rows)
    result = connection.execute(
        cte + "select count(*) from (" + _generic_test_sql(column, name) + ") as generic_result",
        parameters,
    ).fetchone()
    assert result is not None
    return result[0]


def _reconciliation(
    connection: psycopg.Connection,
    rows: tuple[tuple[object, ...], ...],
    *,
    overrides: dict[str, object] | None = None,
    stage_mode: str = "same",
) -> list[tuple[str, int]]:
    cte, parameters = _synthetic_cte(rows, overrides=overrides, stage_mode=stage_mode)
    result = connection.execute(
        cte
        + "select * from ("
        + _render_sql("tests/stg_order_reviews_source_reconciliation.sql")
        + ") as reconciliation_result order by mismatch",
        parameters,
    )
    assert result.description is not None
    assert tuple(column.name for column in result.description) == ("mismatch", "row_count")
    return result.fetchall()


def _assert_flag(projected: dict[str, object], expected: bool = False) -> None:
    assert type(projected[FLAG]) is bool
    assert projected[FLAG] is expected


@pytest.mark.parametrize(
    "source_value,expected,domain_failures,accepted_failures",
    [case[1:] for case in SCORE_CASES],
    ids=[case[0] for case in SCORE_CASES],
)
def test_score_wiring_uses_exact_integer_and_actual_numeric_accepted_values(
    transformer_connection: psycopg.Connection,
    source_value: str,
    expected: int | None,
    domain_failures: int,
    accepted_failures: int,
) -> None:
    row = _source_row({"review_score": source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected["review_score"] == expected
    assert expected is None or type(projected["review_score"]) is int
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == domain_failures
    assert (
        _generic_failures(transformer_connection, (row,), "review_score", "accepted_values")
        == accepted_failures
    )
    if expected is None:
        assert _generic_failures(transformer_connection, (row,), "review_score", "not_null") == 1


@pytest.mark.parametrize(
    "creation,answer,expected_creation,expected_answer,reversed_answer",
    [case[1:] for case in DATE_CASES],
    ids=[case[0] for case in DATE_CASES],
)
def test_ordered_equal_and_reversed_naive_dates_are_retained_without_repair(
    transformer_connection: psycopg.Connection,
    creation: str,
    answer: str,
    expected_creation: datetime,
    expected_answer: datetime,
    reversed_answer: bool,
) -> None:
    row = _source_row({"review_creation_date": creation, "review_answer_timestamp": answer})
    projected = _single_projection(transformer_connection, row)
    assert projected["review_creation_date"] == expected_creation
    assert projected["review_answer_timestamp"] == expected_answer
    for column in DATE_COLUMNS:
        assert type(projected[column]) is datetime
        assert projected[column].tzinfo is None
        assert projected[column].microsecond == 0
    _assert_flag(projected, reversed_answer)
    assert _domain_failures(transformer_connection, row) == 0
    assert _generic_failures(transformer_connection, (row,), FLAG, "not_null") == 0


@pytest.mark.parametrize("column", DATE_COLUMNS)
def test_each_invalid_calendar_date_is_null_blocks_and_does_not_flag_reversal(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: "2018-02-30 03:04:05"})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("column", MANDATORY_SOURCE)
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_each_mandatory_source_absence_is_retained_and_blocks_without_false_reversal(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("column", ("_load_id", "_source_row"))
def test_missing_lineage_is_retained_and_fails_actual_null_and_domain_tests(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: None})
    assert _single_projection(transformer_connection, row)[column] is None
    assert _domain_failures(transformer_connection, row) == 1
    assert _generic_failures(transformer_connection, (row,), column, "not_null") == 1


@pytest.mark.parametrize("column", TEXT_COLUMNS)
@pytest.mark.parametrize("source_value", ["", None], ids=["exact-empty", "raw-null"])
def test_optional_comment_absence_is_null_and_valid_independently(
    transformer_connection: psycopg.Connection, column: str, source_value: str | None
) -> None:
    row = _source_row({column: source_value})
    projected = _single_projection(transformer_connection, row)
    assert projected[column] is None
    other = TEXT_COLUMNS[1] if column == TEXT_COLUMNS[0] else TEXT_COLUMNS[0]
    assert projected[other] == (
        "Linha um\nLinha dois: ótimo!" if other == TEXT_COLUMNS[1] else "Café d'Água"
    )
    _assert_flag(projected)
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize(
    "title,message",
    [("  Café d'Água\nótimo!  ", "Cliente disse: 'bom'\n新しい🙂"), (" \t\n ", "\n\t  ")],
    ids=["unicode-apostrophe-newline", "whitespace-is-source-text"],
)
def test_nonempty_comment_text_is_preserved_without_trimming_or_quote_damage(
    transformer_connection: psycopg.Connection, title: str, message: str
) -> None:
    row = _source_row({"review_comment_title": title, "review_comment_message": message})
    projected = _single_projection(transformer_connection, row)
    assert projected["review_comment_title"] == title
    assert projected["review_comment_message"] == message
    assert _domain_failures(transformer_connection, row) == 0


@pytest.mark.parametrize("column", ("review_id", "order_id"))
def test_literal_uppercase_keys_are_preserved_and_rejected_by_source_domains(
    transformer_connection: psycopg.Connection, column: str
) -> None:
    row = _source_row({column: "D" * 32})
    assert _single_projection(transformer_connection, row)[column] == "D" * 32
    assert _domain_failures(transformer_connection, row) == 1


@pytest.mark.parametrize("order_id,expected", [(ORDER_ID, 0), ("d" * 32, 1)])
def test_actual_order_reference_retains_good_and_missing_parent_review_rows(
    transformer_connection: psycopg.Connection, order_id: str, expected: int
) -> None:
    row = _source_row({"order_id": order_id})
    assert _single_projection(transformer_connection, row)["order_id"] == order_id
    assert _domain_failures(transformer_connection, row) == 0
    assert (
        _generic_failures(transformer_connection, (row,), "order_id", "relationships") == expected
    )


def test_multiple_reviews_per_order_and_reused_review_id_keep_every_pair_and_text(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row({"review_comment_message": "first"}),
        _source_row({"_source_row": 2, "review_id": "d" * 32, "review_comment_message": "second"}),
        _source_row(
            {"_source_row": 3, "order_id": OTHER_ORDER_ID, "review_comment_message": "third"}
        ),
    )
    projected = _projection(transformer_connection, rows, duplicate_parents=True)
    assert [
        (row["review_id"], row["order_id"], row["review_comment_message"]) for row in projected
    ] == [
        (REVIEW_ID, ORDER_ID, "first"),
        ("d" * 32, ORDER_ID, "second"),
        (REVIEW_ID, OTHER_ORDER_ID, "third"),
    ]
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_reviews_grain.sql",
            "duplicate_review_key_groups",
        )
        == 0
    )


def test_duplicate_review_order_pair_is_retained_but_fails_actual_composite_grain(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (_source_row(), _source_row({"_source_row": 2}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_reviews_grain.sql",
            "duplicate_review_key_groups",
        )
        == 1
    )
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_reviews_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == 0
    )


@pytest.mark.parametrize("second_load,expected", [(LOAD, 1), (OTHER_LOAD, 0)])
def test_lineage_uniqueness_is_per_load_and_independent_of_review_order_key(
    transformer_connection: psycopg.Connection, second_load: UUID, expected: int
) -> None:
    rows = (_source_row(), _source_row({"_load_id": second_load, "review_id": "d" * 32}))
    assert len(_projection(transformer_connection, rows)) == 2
    assert (
        _singular_failures(
            transformer_connection,
            rows,
            "stg_order_reviews_lineage_unique.sql",
            "duplicate_lineage_groups",
        )
        == expected
    )


def test_actual_native_reconciliation_passes_exact_unicode_nulls_and_reversal_types(
    transformer_connection: psycopg.Connection,
) -> None:
    rows = (
        _source_row(),
        _source_row(
            {
                "_source_row": 2,
                "review_id": "d" * 32,
                "review_comment_title": "",
                "review_comment_message": None,
                "review_creation_date": "2018-01-03 03:04:05",
                "review_answer_timestamp": "2018-01-02 03:04:05",
            }
        ),
    )
    assert _reconciliation(transformer_connection, rows) == []


@pytest.mark.parametrize(
    "column,replacement",
    [(TEXT_COLUMNS[0], "changed title"), (TEXT_COLUMNS[1], "changed\nmessage"), (FLAG, True)],
    ids=["count-preserving-title-edit", "count-preserving-message-edit", "boolean-flag-edit"],
)
def test_actual_native_reconciliation_blocks_count_preserving_text_or_boolean_corruption(
    transformer_connection: psycopg.Connection, column: str, replacement: object
) -> None:
    assert _reconciliation(
        transformer_connection, (_source_row(),), overrides={column: replacement}
    ) == [("missing_from_staging", 1), ("unexpected_in_staging", 1)]


@pytest.mark.parametrize(
    "source_copies,stage_mode,expected",
    [
        (2, "distinct", [("missing_from_staging", 1)]),
        (1, "duplicate", [("unexpected_in_staging", 1)]),
    ],
    ids=["duplicate-loss", "extra-staged-duplicate"],
)
def test_actual_native_reconciliation_uses_full_row_multisets_not_sets_or_counts(
    transformer_connection: psycopg.Connection,
    source_copies: int,
    stage_mode: str,
    expected: list[tuple[str, int]],
) -> None:
    rows = (_source_row(),) * source_copies
    assert _reconciliation(transformer_connection, rows, stage_mode=stage_mode) == expected


def test_inline_invalid_integer_and_dates_remain_null_with_false_reversal(
    transformer_connection: psycopg.Connection,
) -> None:
    row = _source_row(
        {
            "review_score": "1e99999999999999999999999",
            "review_creation_date": "2018-02-30 03:04:05",
            "review_answer_timestamp": "now",
        }
    )
    projected = _single_projection(transformer_connection, row, materialized=False)
    assert projected["review_score"] is None
    assert all(projected[column] is None for column in DATE_COLUMNS)
    _assert_flag(projected)
