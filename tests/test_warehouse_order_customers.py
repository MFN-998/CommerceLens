"""Execute actual order-customer model/test SQL on query-only synthetic SQLite CTEs.

Installed dbt macros render YAML-configured generics. Python regex and bounded
occurrence-aware EXCEPT ALL adaptation exercise failure logic, not native
PostgreSQL physical types, collation or regular-expression acceptance.
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
COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
CUSTOMERS = (
    (LOAD, 1, "1" * 32, "a" * 32, "00123", " São Paulo🙂 ", "SP"),
    (LOAD, 2, "2" * 32, "a" * 32, "7", " MIXED Case ", "RJ"),
    (OTHER_LOAD, 1, "3" * 32, "a" * 32, "2", "Café d'Água", "AM"),
    (OTHER_LOAD, 2, "4" * 32, "b" * 32, "00001", " ", "MG"),
    (LOAD, 3, "0123456789abcdef" * 2, "b" * 32, "123", "são paulo", "SP"),
)
IDENTITIES = (("a" * 32,), ("b" * 32,))
LOCATIONS = (("00123", True), ("7", False), ("2", False), ("00001", True), ("123", True))
SUBSTITUTIONS = {
    "_load_id": "'22222222-2222-4222-8222-222222222222'",
    "_source_row": "_source_row + 10",
    "customer_id": "'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'",
    "customer_unique_id": "'cccccccccccccccccccccccccccccccc'",
    "customer_zip_code_prefix": "'00124'",
    "customer_city": "customer_city || ' changed'",
    "customer_state": "case when customer_state = 'SP' then 'RJ' else 'SP' end",
}
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join(
        "'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'" if column == "customer_id" else column
        for column in COLUMNS
    )
    + " from projected where customer_id = '11111111111111111111111111111111'"
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
        (PROJECT / "models/intermediate/int_order_customers.yml").read_text("utf-8")
    )["models"][0]


def generic_sql(column: str, name: str) -> str:
    jinja = pytest.importorskip("jinja2")
    tests = next(item["data_tests"] for item in contract()["columns"] if item["name"] == column)
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
        model="int_order_customers", column_name=column, **arguments
    )


def sqlite_except_all(statement: str) -> str:
    """Port this singular test's full-row multiset subtraction without losing NULLs."""

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
    generic: tuple[str, str] | None = None,
    *,
    customers: tuple[tuple[object, ...], ...] = CUSTOMERS,
    identities: tuple[tuple[object, ...], ...] = IDENTITIES,
    locations: tuple[tuple[object, ...], ...] = LOCATIONS,
    changes: dict[str, str] | None = None,
    predicate: str = "true",
    suffix: str = "",
) -> list[tuple[object, ...]]:
    assert not (singular and generic)
    changes = changes or {}
    assert set(changes) <= set(COLUMNS)
    ctes, values = [], []
    for name, columns, rows in (
        ("stg_customers", COLUMNS, customers),
        ("dim_customer", ("customer_unique_id",), identities),
        ("dim_location", ("zip_code_prefix", "has_geolocation"), locations),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/intermediate/int_order_customers.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(
        f"int_order_customers as (select {fields} from projected where {predicate}{suffix})"
    )
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(*generic)
        if generic
        else "select * from int_order_customers"
    )
    statement = sqlite_except_all(
        "with " + ", ".join(ctes) + " select * from (" + query + ") result"
    ).replace(" !~ ", " not regexp ")
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


def test_literal_source_grain_keeps_repeated_identities_addresses_and_load_lineage() -> None:
    assert sorted(run_sql(), key=lambda row: row[2]) == sorted(CUSTOMERS, key=lambda row: row[2])
    assert run_sql("order_customers_domains") == []
    assert run_sql("order_customers_source_reconciliation") == []
    assert run_sql("order_customers_relationships") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
        "uuid",
        "bigint",
        *(["text"] * 5),
    ]
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("customer_id", "unique")) == []
    assert run_sql(generic=("customer_state", "accepted_values")) == []
    identity = next(item for item in contract()["columns"] if item["name"] == "customer_unique_id")
    assert identity["data_tests"] == ["not_null"]


@pytest.mark.parametrize("column", COLUMNS)
def test_installed_required_generics_reject_each_null_output(column: str) -> None:
    changes = {column: "null"}
    assert run_sql(generic=(column, "not_null"), changes=changes)
    assert run_sql("order_customers_source_reconciliation", changes=changes)
    if column in ("_source_row", "customer_id", "customer_unique_id", "customer_zip_code_prefix"):
        assert run_sql("order_customers_domains", changes=changes)


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_every_field_substitution_fails_full_source_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("order_customers_source_reconciliation", changes={column: expression})


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "customer_id <> '33333333333333333333333333333333'"}, (1, 0)),
        ({"suffix": EXTRA_OUTPUT}, (0, 1)),
        (
            {
                "suffix": " union all select * from projected "
                "where customer_id = '11111111111111111111111111111111'"
            },
            (0, 1),
        ),
    ],
)
def test_omitted_extra_or_duplicated_output_records_fail_multiset_reconciliation(
    corruption: dict, expected: tuple[int, int]
) -> None:
    assert run_sql("order_customers_source_reconciliation", **corruption) == [expected]


def test_duplicate_source_customer_id_is_retained_and_blocks_actual_unique_generic() -> None:
    customers = (*CUSTOMERS, CUSTOMERS[0])
    assert len(run_sql(customers=customers)) == 6
    assert run_sql(generic=("customer_id", "unique"), customers=customers) == [("1" * 32, 2)]
    assert run_sql("order_customers_source_reconciliation", customers=customers) == []


@pytest.mark.parametrize("column", ["customer_id", "customer_unique_id"])
@pytest.mark.parametrize(
    "expression",
    [
        "'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'",
        "'１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１'",
        "' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa '",
        "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
        "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' || char(10)",
    ],
)
def test_ascii_lowercase_id_domains_reject_invalid_preserved_output(
    column: str, expression: str
) -> None:
    assert run_sql("order_customers_domains", changes={column: expression})


@pytest.mark.parametrize(
    "column,expression",
    [
        ("customer_zip_code_prefix", "''"),
        ("customer_zip_code_prefix", "'１２３'"),
        ("customer_zip_code_prefix", "'123456'"),
        ("customer_zip_code_prefix", "' 7 '"),
        ("_source_row", "0"),
        ("_source_row", "-1"),
    ],
)
def test_zip_and_positive_ordinal_domains_reject_invalid_preserved_output(
    column: str, expression: str
) -> None:
    assert run_sql("order_customers_domains", changes={column: expression})


@pytest.mark.parametrize("expression", ["'sp'", "'XX'"])
def test_installed_state_accepted_values_generic_blocks_invalid_state(expression: str) -> None:
    assert run_sql(
        generic=("customer_state", "accepted_values"), changes={"customer_state": expression}
    )


@pytest.mark.parametrize(
    "parents,expected",
    [
        ({"identities": IDENTITIES[1:]}, (3, 0)),
        ({"locations": (*LOCATIONS[:2], *LOCATIONS[3:])}, (0, 1)),
        ({"identities": IDENTITIES[:1], "locations": (*LOCATIONS[:2], *LOCATIONS[3:])}, (2, 1)),
    ],
)
def test_absent_required_parents_block_without_filtering_customer_records(
    parents: dict, expected: tuple[int, int]
) -> None:
    assert sorted(run_sql(**parents), key=lambda row: row[2]) == sorted(
        CUSTOMERS, key=lambda row: row[2]
    )
    assert run_sql("order_customers_source_reconciliation", **parents) == []
    assert run_sql("order_customers_relationships", **parents) == [expected]


@pytest.mark.parametrize(
    "parents,expected",
    [
        ({"identities": (("A" * 32,), IDENTITIES[1])}, (3, 0)),
        ({"locations": (LOCATIONS[0], ("00007", False), *LOCATIONS[2:])}, (0, 1)),
    ],
)
def test_required_parent_matching_is_literal_without_case_conversion_or_zip_padding(
    parents: dict, expected: tuple[int, int]
) -> None:
    assert run_sql("order_customers_relationships", **parents) == [expected]


def test_existing_locations_without_geolocation_are_valid_required_references() -> None:
    locations = tuple((prefix, False) for prefix, _ in LOCATIONS)
    assert run_sql("order_customers_relationships", locations=locations) == []
    assert len(run_sql(locations=locations)) == len(CUSTOMERS)


def test_duplicate_parent_rows_do_not_fan_out_the_unchanged_source_projection() -> None:
    parents = {
        "identities": (*IDENTITIES, IDENTITIES[0]),
        "locations": (*LOCATIONS, LOCATIONS[0]),
    }
    assert sorted(run_sql(**parents), key=lambda row: row[2]) == sorted(
        CUSTOMERS, key=lambda row: row[2]
    )
    assert run_sql("order_customers_relationships", **parents) == []


def test_invalid_source_values_and_missing_city_are_retained_to_block_validation() -> None:
    invalid = (LOAD, 0, "INVALID", None, "１２３", None, "sp")
    customers = (invalid,)
    assert run_sql(customers=customers) == [invalid]
    assert run_sql("order_customers_domains", customers=customers) == [(1,)]
    assert run_sql(generic=("customer_city", "not_null"), customers=customers) == [(None,)]
    assert run_sql(generic=("customer_state", "accepted_values"), customers=customers)
    assert run_sql("order_customers_source_reconciliation", customers=customers) == []


def test_empty_source_produces_empty_valid_order_customer_mapping() -> None:
    assert run_sql(customers=()) == []
    for singular in (
        "order_customers_domains",
        "order_customers_source_reconciliation",
        "order_customers_relationships",
    ):
        assert run_sql(singular, customers=()) == []
    for column in COLUMNS:
        assert run_sql(generic=(column, "not_null"), customers=()) == []
    assert run_sql(generic=("customer_id", "unique"), customers=()) == []
    assert run_sql(generic=("customer_state", "accepted_values"), customers=()) == []
