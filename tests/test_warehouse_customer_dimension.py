"""Execute actual customer dimension/test SQL on query-only synthetic SQLite CTEs.

Installed dbt macros render the YAML-configured generic tests. The bounded
occurrence-aware EXCEPT ALL port and Python regex bridge exercise failure logic;
they do not prove native PostgreSQL types, collation, regex or EXCEPT ALL behavior.
No private configuration, network, datasets or persistent fixture tables are used.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"
LOAD = "11111111-1111-4111-8111-111111111111"
OTHER_LOAD = "22222222-2222-4222-8222-222222222222"
SOURCE_COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
CUSTOMERS = (
    (LOAD, 1, "1" * 32, "a" * 32, "00123", "São Paulo🙂", "SP"),
    (LOAD, 2, "2" * 32, "a" * 32, "7", "  Mixed CASE  ", "RJ"),
    (LOAD, 3, "3" * 32, "b" * 32, "00001", "sao paulo", "SP"),
    (OTHER_LOAD, 1, "4" * 32, "a" * 32, "9", "Café d'Água", "AM"),
    (OTHER_LOAD, 2, "5" * 32, "b" * 32, "2", "Other City", "MG"),
    (OTHER_LOAD, 3, "6" * 32, "0123456789abcdef" * 2, "123", "Last City", "BA"),
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
        (PROJECT / "models/core/dim_customer.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(name: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = contract()["columns"][0]["data_tests"]
    definition = next(
        test for test in tests if test == name or isinstance(test, dict) and name in test
    )
    arguments = dict(definition[name]["arguments"]) if isinstance(definition, dict) else {}
    spec = importlib.util.find_spec("dbt.include.global_project")
    assert spec is not None and spec.origin is not None
    macro = Path(spec.origin).parent / "macros/generic_test_sql" / (name + ".sql")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    module = environment.from_string(macro.read_text("utf-8")).make_module(
        {"should_store_failures": lambda: False}
    )
    return getattr(module, "default__test_" + name)(
        model="dim_customer", column_name="customer_unique_id", **arguments
    )


def sqlite_except_all(statement: str) -> str:
    """Port only this singular test's one-column multiset subtraction to SQLite."""

    def subtract(match: re.Match[str]) -> str:
        left, right = match.groups()
        return (
            "select l.customer_unique_id from "
            "(select *, row_number() over (partition by customer_unique_id collate C) "
            f"as occurrence from {left}) l left join "
            "(select *, row_number() over (partition by customer_unique_id collate C) "
            f"as occurrence from {right}) r "
            "on l.customer_unique_id is r.customer_unique_id "
            "and l.occurrence = r.occurrence where r.occurrence is null"
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
    customers: tuple[tuple[object, ...], ...] = CUSTOMERS,
    identity: str | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    selection = (
        "values " + ", ".join("(" + ", ".join("?" for _ in SOURCE_COLUMNS) + ")" for _ in customers)
        if customers
        else "select " + ", ".join("null" for _ in SOURCE_COLUMNS) + " where false"
    )
    fields = "*" if identity is None else identity + " as customer_unique_id"
    ctes = [
        f"stg_customers ({', '.join(SOURCE_COLUMNS)}) as ({selection})",
        "projected as (" + render("models/core/dim_customer.sql") + ")",
        f"dim_customer as (select {fields} from projected where {predicate}{suffix})",
    ]
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(generic)
        if generic
        else "select * from dim_customer"
    )
    statement = sqlite_except_all(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    ).replace(" !~ ", " not regexp ")
    values = tuple(value for row in customers for value in row)
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
            assert tuple(column[0] for column in result.description) == ("customer_unique_id",)
        return result.fetchall()


def test_customer_identity_grain_spans_source_customers_addresses_and_loads() -> None:
    assert sorted(run_sql()) == [("0123456789abcdef" * 2,), ("a" * 32,), ("b" * 32,)]
    assert run_sql("customer_dimension_domains") == []
    assert run_sql("customer_dimension_source_reconciliation") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert [(item["name"], item["data_type"]) for item in contract()["columns"]] == [
        ("customer_unique_id", "text")
    ]
    for generic in ("not_null", "unique"):
        assert run_sql(generic=generic) == []


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        " " + "a" * 32 + " ",
        "a" * 31,
        "a" * 33,
        "A" * 32,
        "g" * 32,
        "é" * 32,
        "１" * 32,
        "a" * 32 + "\n",
    ],
)
def test_invalid_literal_identities_are_retained_once_and_block_validation(value: object) -> None:
    customers = (
        *CUSTOMERS,
        (LOAD, 4, "7" * 32, value, "00123", "First invalid address", "SP"),
        (OTHER_LOAD, 4, "8" * 32, value, "9", "Different invalid address", "RJ"),
    )
    result = run_sql(customers=customers)
    assert len(result) == 4
    assert set(result) == {("a" * 32,), ("b" * 32,), ("0123456789abcdef" * 2,), (value,)}
    assert run_sql("customer_dimension_source_reconciliation", customers=customers) == []
    assert run_sql("customer_dimension_domains", customers=customers) == [(1,)]
    assert run_sql(generic="not_null", customers=customers) == ([(None,)] if value is None else [])


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "customer_unique_id <> '0123456789abcdef0123456789abcdef'"}, (1, 0)),
        ({"suffix": " union all select 'dddddddddddddddddddddddddddddddd'"}, (0, 1)),
        (
            {
                "identity": (
                    "case when customer_unique_id = '0123456789abcdef0123456789abcdef' "
                    "then 'dddddddddddddddddddddddddddddddd' else customer_unique_id end"
                )
            },
            (1, 1),
        ),
        (
            {
                "suffix": (
                    " union all select * from projected "
                    "where customer_unique_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
                )
            },
            (0, 1),
        ),
    ],
)
def test_missing_extra_changed_and_duplicated_identities_fail_reconciliation(
    corruption: dict, expected: tuple[int, int]
) -> None:
    assert run_sql("customer_dimension_source_reconciliation", **corruption) == [expected]


def test_installed_unique_generic_rejects_duplicate_output_identity() -> None:
    suffix = (
        " union all select * from projected "
        "where customer_unique_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
    )
    assert run_sql(generic="unique", suffix=suffix) == [("a" * 32, 2)]


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "customer_unique_id is not null"}, (1, 0)),
        ({"suffix": " union all select * from projected"}, (0, 1)),
        ({"identity": "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"}, (1, 1)),
    ],
)
def test_null_identity_multiset_differences_are_detected(
    corruption: dict, expected: tuple[int, int]
) -> None:
    customers = (
        (LOAD, 1, "1" * 32, None, "00123", "First City", "SP"),
        (OTHER_LOAD, 1, "2" * 32, None, "7", "Other City", "RJ"),
    )
    assert run_sql(customers=customers) == [(None,)]
    assert run_sql("customer_dimension_source_reconciliation", customers=customers) == []
    assert run_sql(
        "customer_dimension_source_reconciliation", customers=customers, **corruption
    ) == [expected]


def test_empty_source_produces_empty_valid_customer_dimension() -> None:
    assert run_sql(customers=()) == []
    assert run_sql("customer_dimension_domains", customers=()) == []
    assert run_sql("customer_dimension_source_reconciliation", customers=()) == []
    for generic in ("not_null", "unique"):
        assert run_sql(generic=generic, customers=()) == []
