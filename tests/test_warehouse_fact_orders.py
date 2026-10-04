"""Execute actual fact-order model/test SQL with query-only synthetic SQLite CTEs.

Configured generics render installed dbt macros. Bounded date-cast, Python regex
and occurrence-aware EXCEPT ALL adaptations exercise SQL failure logic; native
PostgreSQL remains authoritative for physical types, collation and timestamps.
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
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
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
EVENTS = SOURCE_COLUMNS[5:10]
ENRICHMENT = (
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
COLUMNS = (*SOURCE_COLUMNS, *ENRICHMENT, *DATE_COLUMNS)
REQUIRED = (*SOURCE_COLUMNS[:6], *SOURCE_COLUMNS[9:], *ENRICHMENT, DATE_COLUMNS[0], DATE_COLUMNS[4])
CUSTOMER_COLUMNS = (
    "_load_id",
    "_source_row",
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
)
ORDERS = (
    (
        LOAD,
        10,
        "a" * 32,
        "1" * 32,
        "delivered",
        "2018-01-10 23:59:59",
        "2018-01-11 00:00:00",
        "2018-01-12 04:05:06",
        "2018-01-13 12:34:56",
        "2018-01-14 00:00:00",
        *([False] * 12),
    ),
    (
        OTHER_LOAD,
        1,
        "b" * 32,
        "2" * 32,
        "canceled",
        "2018-02-28 23:59:59",
        None,
        None,
        None,
        "2018-03-10 00:00:00",
        True,
        True,
        True,
        *([False] * 9),
    ),
    (
        LOAD,
        11,
        "c" * 32,
        "3" * 32,
        "unavailable",
        "2020-04-09 23:59:59",
        "2020-04-08 03:04:05",
        "2020-04-07 02:03:04",
        "2020-04-06 01:02:03",
        "2020-04-10 00:00:00",
        *([False] * 6),
        *([True] * 6),
    ),
)
CUSTOMERS = (
    (OTHER_LOAD, 100, "1" * 32, "e" * 32, "00123", " São Paulo🙂 ", "SP"),
    (LOAD, 200, "2" * 32, "e" * 32, "7", " MIXED Case ", "RJ"),
    (OTHER_LOAD, 101, "3" * 32, "f" * 32, "2", " ", "AM"),
)
IDENTITIES = (("e" * 32,), ("f" * 32,))
LOCATIONS = (("00123", True), ("7", False), ("2", False))
DATES = (
    ("2018-01-10",),
    ("2018-01-11",),
    ("2018-01-12",),
    ("2018-01-13",),
    ("2018-01-14",),
    ("2018-02-28",),
    ("2018-03-10",),
    ("2020-04-06",),
    ("2020-04-07",),
    ("2020-04-08",),
    ("2020-04-09",),
    ("2020-04-10",),
)
EXPECTED = (
    (
        *ORDERS[0],
        "e" * 32,
        "00123",
        " São Paulo🙂 ",
        "SP",
        OTHER_LOAD,
        100,
        "2018-01-10",
        "2018-01-11",
        "2018-01-12",
        "2018-01-13",
        "2018-01-14",
    ),
    (
        *ORDERS[1],
        "e" * 32,
        "7",
        " MIXED Case ",
        "RJ",
        LOAD,
        200,
        "2018-02-28",
        None,
        None,
        None,
        "2018-03-10",
    ),
    (
        *ORDERS[2],
        "f" * 32,
        "2",
        " ",
        "AM",
        OTHER_LOAD,
        101,
        "2020-04-09",
        "2020-04-08",
        "2020-04-07",
        "2020-04-06",
        "2020-04-10",
    ),
)
SUBSTITUTIONS = {
    "_load_id": "'33333333-3333-4333-8333-333333333333'",
    "_source_row": "_source_row + 1",
    "order_id": "'dddddddddddddddddddddddddddddddd'",
    "customer_id": "'44444444444444444444444444444444'",
    "order_status": "'created'",
    **{column: "'2001-01-01 01:02:03'" for column in EVENTS},
    **{column: "not " + column for column in SOURCE_COLUMNS[10:]},
    "customer_unique_id": "'dddddddddddddddddddddddddddddddd'",
    "customer_zip_code_prefix": "'00124'",
    "customer_city": "customer_city || ' changed'",
    "customer_state": "'MG'",
    "customer_load_id": "'33333333-3333-4333-8333-333333333333'",
    "customer_source_row": "customer_source_row + 1",
    **{column: "'2001-01-01'" for column in DATE_COLUMNS},
}
EXTRA_OUTPUT = (
    " union all select "
    + ", ".join(
        "'dddddddddddddddddddddddddddddddd'" if column == "order_id" else column
        for column in COLUMNS
    )
    + " from projected where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
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
        (PROJECT / "models/core/fact_orders.yml").read_text("utf-8")
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
        model="fact_orders", column_name=column, **arguments
    )


def sqlite_statement(statement: str) -> str:
    """Adapt only the actual SQL's five timestamp-to-date casts and EXCEPT ALL."""
    statement = re.sub(
        r"cast\(((?:o\.)?(?:" + "|".join(EVENTS) + r")) as date\)",
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
    generic: tuple[str, str] | None = None,
    *,
    orders: tuple[tuple[object, ...], ...] = ORDERS,
    customers: tuple[tuple[object, ...], ...] = CUSTOMERS,
    identities: tuple[tuple[object, ...], ...] = IDENTITIES,
    locations: tuple[tuple[object, ...], ...] = LOCATIONS,
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
        ("stg_orders", SOURCE_COLUMNS, orders),
        ("int_order_customers", CUSTOMER_COLUMNS, customers),
        ("dim_customer", ("customer_unique_id",), identities),
        ("dim_location", ("zip_code_prefix", "has_geolocation"), locations),
        ("dim_date", ("calendar_date",), dates),
    ):
        selection = (
            "values " + ", ".join("(" + ", ".join("?" for _ in columns) + ")" for _ in rows)
            if rows
            else "select " + ", ".join("null" for _ in columns) + " where false"
        )
        ctes.append(f"{name} ({', '.join(columns)}) as ({selection})")
        values.extend(value for row in rows for value in row)
    ctes.append("projected as (" + render("models/core/fact_orders.sql") + ")")
    fields = (
        ", ".join(changes.get(column, column) + " as " + column for column in COLUMNS)
        if changes
        else "*"
    )
    ctes.append(f"fact_orders as (select {fields} from projected where {predicate}{suffix})")
    query = (
        render("tests/" + singular + ".sql")
        if singular
        else generic_sql(*generic)
        if generic
        else "select * from fact_orders"
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


def test_fact_preserves_all_source_fields_mapping_addresses_lineage_and_calendar_roles() -> None:
    assert sorted(run_sql(), key=lambda row: row[2]) == list(EXPECTED)
    assert run_sql("fact_orders_domains") == []
    assert run_sql("fact_orders_source_reconciliation") == []
    assert run_sql("fact_orders_relationships") == []
    assert contract()["config"] == {"materialized": "view", "schema": "core"}
    assert tuple(item["name"] for item in contract()["columns"]) == COLUMNS
    assert [item["data_type"] for item in contract()["columns"]] == [
        "uuid",
        "bigint",
        *(["text"] * 3),
        *(["timestamp without time zone"] * 5),
        *(["boolean"] * 12),
        *(["text"] * 4),
        "uuid",
        "bigint",
        *(["date"] * 5),
    ]
    for column in REQUIRED:
        assert run_sql(generic=(column, "not_null")) == []
    assert run_sql(generic=("order_id", "unique")) == []
    for column in ("order_status", "customer_state"):
        assert run_sql(generic=(column, "accepted_values")) == []
    for column in (*EVENTS[1:4], *DATE_COLUMNS[1:4]):
        assert "data_tests" not in next(
            item for item in contract()["columns"] if item["name"] == column
        )


@pytest.mark.parametrize("column", REQUIRED)
def test_each_required_null_output_fails_the_installed_generic(column: str) -> None:
    changes = {column: "null"}
    assert run_sql(generic=(column, "not_null"), changes=changes)
    assert run_sql("fact_orders_source_reconciliation", changes=changes)
    if column in (
        "order_id",
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "_source_row",
        "customer_source_row",
    ):
        assert run_sql("fact_orders_domains", changes=changes)


@pytest.mark.parametrize("column,expression", SUBSTITUTIONS.items())
def test_every_source_mapping_or_calendar_field_change_fails_full_reconciliation(
    column: str, expression: str
) -> None:
    assert run_sql("fact_orders_source_reconciliation", changes={column: expression})


def test_missing_customer_mapping_retains_order_and_blocks_required_reference_and_fields() -> None:
    customers = CUSTOMERS[1:]
    result = sorted(run_sql(customers=customers), key=lambda row: row[2])
    assert result[0] == (*ORDERS[0], *([None] * 6), *EXPECTED[0][-5:])
    assert len(result) == len(ORDERS)
    assert run_sql("fact_orders_source_reconciliation", customers=customers) == []
    assert run_sql("fact_orders_relationships", customers=customers) == [(1, 1, 1, 0)]
    assert run_sql("fact_orders_domains", customers=customers) == [(1,)]
    for column in ENRICHMENT:
        assert run_sql(generic=(column, "not_null"), customers=customers) == [(None,)]


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_mapping_fanout_is_blocked_even_when_expected_join_also_fans_out(
    conflicting: bool,
) -> None:
    duplicate = (
        (*CUSTOMERS[0][:5], "Conflicting address", CUSTOMERS[0][-1])
        if conflicting
        else CUSTOMERS[0]
    )
    customers = (*CUSTOMERS, duplicate)
    assert len(run_sql(customers=customers)) == 4
    assert run_sql(generic=("order_id", "unique"), customers=customers) == [("a" * 32, 2)]
    assert run_sql("fact_orders_source_reconciliation", customers=customers) == [(3, 4, 0, 0)]


@pytest.mark.parametrize(
    "parents,expected",
    [
        ({"identities": IDENTITIES[:1]}, (0, 1, 0, 0)),
        ({"locations": (LOCATIONS[0], LOCATIONS[2])}, (0, 0, 1, 0)),
    ],
)
def test_missing_identity_or_location_dimension_blocks_without_filtering_orders(
    parents: dict, expected: tuple[int, int, int, int]
) -> None:
    assert sorted(run_sql(**parents), key=lambda row: row[2]) == list(EXPECTED)
    assert run_sql("fact_orders_relationships", **parents) == [expected]


@pytest.mark.parametrize(
    "parents,expected",
    [
        (
            {
                "customers": (
                    (*CUSTOMERS[0][:2], " 11111111111111111111111111111111 ", *CUSTOMERS[0][3:]),
                    *CUSTOMERS[1:],
                )
            },
            (1, 1, 1, 0),
        ),
        ({"identities": (("E" * 32,), IDENTITIES[1])}, (0, 2, 0, 0)),
        ({"locations": (LOCATIONS[0], ("00007", False), LOCATIONS[2])}, (0, 0, 1, 0)),
    ],
)
def test_parent_join_and_membership_use_literal_keys_without_padding_or_case_conversion(
    parents: dict, expected: tuple[int, int, int, int]
) -> None:
    assert len(run_sql(**parents)) == len(ORDERS)
    assert run_sql("fact_orders_relationships", **parents) == [expected]


@pytest.mark.parametrize("role", range(5))
def test_missing_date_parent_at_every_recorded_role_blocks_without_dropping_order(
    role: int,
) -> None:
    missing_date = EXPECTED[0][-5 + role]
    dates = tuple(row for row in DATES if row[0] != missing_date)
    assert sorted(run_sql(dates=dates), key=lambda row: row[2]) == list(EXPECTED)
    assert run_sql("fact_orders_relationships", dates=dates) == [(0, 0, 0, 1)]


@pytest.mark.parametrize("column", DATE_COLUMNS)
def test_null_calendar_key_for_recorded_timestamp_fails_null_safe_correspondence(
    column: str,
) -> None:
    changes = {column: "null"}
    assert run_sql("fact_orders_domains", orders=ORDERS[:1], changes=changes) == [(1,)]
    assert run_sql("fact_orders_source_reconciliation", orders=ORDERS[:1], changes=changes) == [
        (1, 1, 1, 1)
    ]


@pytest.mark.parametrize("column", DATE_COLUMNS[1:4])
def test_spurious_calendar_key_for_absent_optional_timestamp_fails_correspondence(
    column: str,
) -> None:
    changes = {column: "'2018-02-28'"}
    assert run_sql("fact_orders_domains", orders=ORDERS[1:2], changes=changes) == [(1,)]
    assert run_sql("fact_orders_relationships", orders=ORDERS[1:2], changes=changes) == []


@pytest.mark.parametrize(
    "column,expression",
    [
        ("order_id", "'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'"),
        ("order_id", "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"),
        ("customer_id", "' 11111111111111111111111111111111 '"),
        (
            "customer_id",
            "'１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１１'",
        ),
        ("customer_unique_id", "'gggggggggggggggggggggggggggggggg'"),
        ("customer_unique_id", "'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee' || char(10)"),
        ("customer_zip_code_prefix", "'１２３'"),
        ("customer_zip_code_prefix", "' 7 '"),
        ("customer_zip_code_prefix", "'123456'"),
        ("_source_row", "0"),
        ("_source_row", "-1"),
        ("customer_source_row", "0"),
        ("customer_source_row", "-1"),
    ],
)
def test_key_zip_and_both_lineage_ordinal_domains_reject_invalid_retained_output(
    column: str, expression: str
) -> None:
    assert run_sql("fact_orders_domains", changes={column: expression})


@pytest.mark.parametrize(
    "column,expression",
    [
        ("order_status", "'DELIVERED'"),
        ("order_status", "'unknown'"),
        ("customer_state", "'sp'"),
        ("customer_state", "'XX'"),
    ],
)
def test_installed_status_and_state_generics_reject_invalid_literal_values(
    column: str, expression: str
) -> None:
    assert run_sql(generic=(column, "accepted_values"), changes={column: expression})


@pytest.mark.parametrize(
    "corruption,expected",
    [
        ({"predicate": "order_id <> 'cccccccccccccccccccccccccccccccc'"}, (3, 2, 1, 0)),
        ({"suffix": EXTRA_OUTPUT}, (3, 4, 0, 1)),
        (
            {
                "suffix": " union all select * from projected "
                "where order_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
            },
            (3, 4, 0, 1),
        ),
    ],
)
def test_omitted_reversed_order_extra_or_duplicate_output_fails_conservation(
    corruption: dict, expected: tuple[int, int, int, int]
) -> None:
    assert run_sql("fact_orders_source_reconciliation", **corruption) == [expected]


def test_duplicate_source_order_is_retained_and_blocks_unique_grain_test() -> None:
    orders = (*ORDERS, ORDERS[0])
    assert len(run_sql(orders=orders)) == 4
    assert run_sql(generic=("order_id", "unique"), orders=orders) == [("a" * 32, 2)]
    assert run_sql("fact_orders_source_reconciliation", orders=orders) == []


def test_empty_typed_input_relations_produce_empty_valid_fact() -> None:
    inputs = {"orders": (), "customers": (), "identities": (), "locations": (), "dates": ()}
    assert run_sql(**inputs) == []
    for singular in (
        "fact_orders_domains",
        "fact_orders_source_reconciliation",
        "fact_orders_relationships",
    ):
        assert run_sql(singular, **inputs) == []
    for column in REQUIRED:
        assert run_sql(generic=(column, "not_null"), **inputs) == []
    assert run_sql(generic=("order_id", "unique"), **inputs) == []
