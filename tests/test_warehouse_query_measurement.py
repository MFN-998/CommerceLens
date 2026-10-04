"""Offline regressions for retained operational summaries and explicit execution.

Synthetic plans check PostgreSQL's inclusive buffer accounting and local worker
spill statistics. No private configuration, connection, source rows or artifacts
are read or written; the execution entry point is replaced in every CLI test.
"""

import json
from copy import deepcopy
from decimal import Decimal

import pytest

from scripts import measure_warehouse_queries as measurement

PRIVATE_DETAIL = "synthetic-private-driver-or-source-detail"


@pytest.fixture(autouse=True)
def forbid_unstubbed_measurement(monkeypatch):
    def unexpected():
        pytest.fail("Offline tests reached an unstubbed warehouse measurement")

    monkeypatch.setattr(measurement, "measure", unexpected)


def plan(root):
    return {"Plan": root, "Planning Time": 1.25, "Execution Time": 8.5}


def test_summary_uses_inclusive_root_buffers_without_summing_children_or_workers() -> None:
    explanation = plan(
        {
            "Node Type": "Gather",
            "Actual Rows": 3,
            "Shared Hit Blocks": 100,
            "Shared Read Blocks": 11,
            "Shared Dirtied Blocks": 2,
            "Shared Written Blocks": 1,
            "Temp Read Blocks": 40,
            "Temp Written Blocks": 50,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Shared Hit Blocks": 100,
                    "Shared Read Blocks": 11,
                    "Temp Read Blocks": 40,
                    "Temp Written Blocks": 50,
                    "Workers": [{"Worker Number": 0, "Shared Hit Blocks": 80}],
                }
            ],
        }
    )
    summary = measurement.summarize_plan(explanation)
    assert summary["root_buffers"] == {
        "Shared Hit Blocks": 100,
        "Shared Read Blocks": 11,
        "Shared Dirtied Blocks": 2,
        "Shared Written Blocks": 1,
        "Temp Read Blocks": 40,
        "Temp Written Blocks": 50,
    }
    assert summary["node_types"] == {"Gather": 1, "Seq Scan": 1}
    assert summary["output_rows"] == 3


@pytest.mark.parametrize("parallel", [False, True])
def test_summary_includes_serial_and_parallel_worker_sort_and_hash_spills(parallel) -> None:
    sort = {
        "Node Type": "Sort",
        "Sort Space Type": "Disk",
        "Sort Space Used": 64,
        "Plans": [{"Node Type": "Hash", "Hash Batches": 8}],
    }
    aggregate = {
        "Node Type": "Aggregate",
        "Actual Rows": 3,
        "HashAgg Batches": 4,
        "Disk Usage": 128,
        "Plans": [sort],
    }
    if parallel:
        sort["Workers"] = [
            {"Worker Number": 0, "Sort Space Type": "Disk", "Sort Space Used": 96},
            {"Worker Number": 1, "Sort Space Type": "Memory", "Sort Space Used": 999},
        ]
        aggregate["Workers"] = [
            {"Worker Number": 0, "HashAgg Batches": 16, "Disk Usage": 32},
            {"Worker Number": 1, "HashAgg Batches": 1, "Disk Usage": 0},
        ]
    summary = measurement.summarize_plan(plan(aggregate))
    assert summary["disk_sort_instances"] == (2 if parallel else 1)
    assert summary["sort_disk_kb"] == (160 if parallel else 64)
    assert summary["max_hash_batches"] == (16 if parallel else 8)
    assert summary["hash_disk_kb"] == (160 if parallel else 128)


def test_summary_defaults_absent_optional_buffers_workers_and_spills_to_zero() -> None:
    summary = measurement.summarize_plan(plan({"Node Type": "Result", "Actual Rows": 0}))
    assert summary["planning_ms"] == 1.25
    assert summary["execution_ms"] == 8.5
    assert summary["output_rows"] == 0
    assert set(summary["root_buffers"].values()) == {0}
    for name in ("disk_sort_instances", "sort_disk_kb", "max_hash_batches", "hash_disk_kb"):
        assert summary[name] == 0


def test_summary_omits_sql_conditions_outputs_and_source_values_without_mutating_plan() -> None:
    explanation = plan(
        {
            "Node Type": "Result",
            "Actual Rows": 1,
            "Output": [PRIVATE_DETAIL],
            "Filter": PRIVATE_DETAIL,
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Index Cond": PRIVATE_DETAIL,
                    "Hash Cond": PRIVATE_DETAIL,
                    "Join Filter": PRIVATE_DETAIL,
                    "Workers": [{"Worker Number": 0, "Output": [PRIVATE_DETAIL]}],
                }
            ],
        }
    )
    explanation["Query Text"] = PRIVATE_DETAIL
    explanation["source_records"] = [{"order_id": PRIVATE_DETAIL}]
    original = deepcopy(explanation)
    summary = measurement.summarize_plan(explanation)
    retained = json.dumps(summary)
    assert PRIVATE_DETAIL not in retained
    assert "order_id" not in retained
    assert set(summary) == {
        "planning_ms",
        "execution_ms",
        "output_rows",
        "node_types",
        "root_buffers",
        "disk_sort_instances",
        "sort_disk_kb",
        "max_hash_batches",
        "hash_disk_kb",
    }
    assert explanation == original


def test_rollup_preserves_absence_measured_zero_and_exact_decimal_amounts() -> None:
    fields = ("order_count", "source_price_sum", "source_freight_sum", "source_payment_sum")
    empty = measurement._rollup([], fields)
    assert empty == dict.fromkeys(fields, None) | {"order_count": 0}
    rows = [
        {
            "order_count": 1,
            "source_price_sum": None,
            "source_freight_sum": None,
            "source_payment_sum": Decimal("0.00"),
        },
        {
            "order_count": 2,
            "source_price_sum": Decimal("9007199254740992.10"),
            "source_freight_sum": None,
            "source_payment_sum": None,
        },
        {
            "order_count": 1,
            "source_price_sum": Decimal("0.20"),
            "source_freight_sum": None,
            "source_payment_sum": None,
        },
    ]
    rolled = measurement._rollup(rows, fields)
    assert rolled == {
        "order_count": 4,
        "source_price_sum": Decimal("9007199254740992.30"),
        "source_freight_sum": None,
        "source_payment_sum": Decimal("0.00"),
    }
    assert isinstance(rolled["source_price_sum"], Decimal)
    assert isinstance(rolled["source_payment_sum"], Decimal)


@pytest.mark.parametrize("arguments", [[], ["--run", "--extra"]])
def test_cli_requires_exact_run_opt_in_before_measurement(arguments, capsys) -> None:
    assert measurement.main(arguments) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Use --run to opt into bounded read-only query measurements.\n"


@pytest.mark.parametrize(
    "error,status,message",
    [
        (
            RuntimeError,
            1,
            "Measurement failed; preserve artifacts. No private error detail logged.",
        ),
        (
            KeyboardInterrupt,
            130,
            "Measurement interrupted; preserve partial artifacts and inspect their receipt.",
        ),
    ],
)
def test_cli_measurement_failure_never_prints_private_exception_detail(
    monkeypatch, capsys, error, status, message
) -> None:
    def failing():
        raise error(PRIVATE_DETAIL)

    monkeypatch.setattr(measurement, "measure", failing)
    assert measurement.main(["--run"]) == status
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == message + "\n"
    assert PRIVATE_DETAIL not in captured.err


def test_cli_reports_success_only_after_measurement_returns(monkeypatch, capsys) -> None:
    result = {"complete": True, "database_bytes": 123}

    def finished():
        captured = capsys.readouterr()
        assert captured.out == captured.err == ""
        return result

    monkeypatch.setattr(measurement, "measure", finished)
    assert measurement.main(["--run"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    assert captured.err == ""
