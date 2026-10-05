"""Fixed native final checks for one approved isolated reconstruction target.

The 600-second budget passed dated fresh-target verification on 2026-10-05.
See docs/warehouse-reconstruction-verification.json. These checks reuse
accepted SQL/oracles; they do not repeat empty-target fixtures or measure plans.
Prior boundary evidence applies to accepted PostgreSQL 17. A different server
version requires boundary re-evaluation before relying on these final checks.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.warehouse.config import ROOT, WarehousePurpose
from src.warehouse.dbt_reconstruction import _contained
from src.warehouse.reconstruction import _isolated_root, _settings

MODULE_STEMS = (
    "category_translation",
    "customer",
    "customer_dimension",
    "date_dimension",
    "geolocation",
    "item",
    "location",
    "order",
    "payment",
    "product",
    "product_dimension",
    "review",
    "seller",
    "seller_dimension",
    "order_customers",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "fact_reviews",
    "order_components",
    "query_examples_postgres",
    "mart_reader",
)
TEST_FILES = tuple(f"test_warehouse_{name}_integration.py" for name in MODULE_STEMS)
OPT_IN_NAMES = tuple(
    "COMMERCE_WAREHOUSE_"
    + {
        "fact_order_items": "FACT_ITEMS",
        "query_examples_postgres": "QUERY_EXAMPLES",
    }.get(name, name.upper())
    + "_INTEGRATION"
    for name in MODULE_STEMS
)
ACCEPTANCE_TIMEOUT_SECONDS = 600
FAILURE_MESSAGE = "Isolated reconstruction acceptance failed; artifacts retained; no detail logged"
WORKER_BOOTSTRAP = (
    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
    "from src.warehouse.reconstruction_acceptance import _worker; "
    "raise SystemExit(_worker(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])))"
)


class ReconstructionAcceptanceError(ValueError):
    """Fixed safe diagnostics without driver, fixture or source details."""


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    temporary = path.with_name("receipt-" + uuid4().hex + ".pending")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _verify_receipt(path: Path, expected_ref: str) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or set(receipt) != {
        "status",
        "project_ref",
        "files",
        "collected",
        "passed",
        "errors",
    }:
        raise ValueError
    files = receipt["files"]
    if (
        receipt["status"] != "passed"
        or receipt["project_ref"] != expected_ref
        or not isinstance(files, dict)
        or set(files) != set(TEST_FILES)
        or any(type(count) is not int or count <= 0 for count in files.values())
    ):
        raise ValueError
    if (
        type(receipt["collected"]) is not int
        or type(receipt["passed"]) is not int
        or type(receipt["errors"]) is not int
        or receipt["errors"] != 0
        or sum(files.values()) != receipt["collected"]
        or receipt["passed"] != receipt["collected"]
    ):
        raise ValueError
    return receipt


class _AcceptancePlugin:
    """Route only selected module settings and retain no test/driver output."""

    def __init__(self, settings_root: Path, expected_project_ref: str, receipt_path: Path):
        self.settings_root, self.expected_ref, self.receipt_path = (
            settings_root,
            expected_project_ref,
            receipt_path,
        )
        self.files: dict[str, int] = {}
        self.reports: dict[str, set[str]] = {}
        self.calls: set[str] = set()
        self.errors = 0

    def load_settings(self, *args: object, purpose: WarehousePurpose = "admin", **kwargs: object):
        if args or kwargs or purpose not in ("admin", "transformer"):
            raise ReconstructionAcceptanceError(FAILURE_MESSAGE)
        return _settings(self.settings_root, purpose, self.expected_ref)

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        for item in items:
            path = Path(item.module.__file__).resolve()
            if (
                path.parent != (ROOT / "tests").resolve()
                or path.name not in TEST_FILES
                or not isinstance(item.nodeid, str)
                or item.nodeid in self.reports
                or {"tmp_path", "tmp_path_factory"}.intersection(item.fixturenames)
            ):
                self.errors += 1
                raise ReconstructionAcceptanceError(FAILURE_MESSAGE)
            self.files[path.name] = self.files.get(path.name, 0) + 1
            self.reports[item.nodeid] = set()
            item.module.load_settings = self.load_settings
        if set(self.files) != set(TEST_FILES):
            self.errors += 1
            raise ReconstructionAcceptanceError(FAILURE_MESSAGE)

    @pytest.hookimpl(tryfirst=True)
    def pytest_fixture_setup(self, fixturedef: Any, request: Any) -> None:
        if fixturedef.argname in ("tmp_path", "tmp_path_factory"):
            self.errors += 1
            raise ReconstructionAcceptanceError(FAILURE_MESSAGE)

    def pytest_runtest_logreport(self, report: Any) -> None:
        phases = self.reports.get(report.nodeid)
        if (
            phases is None
            or report.when not in ("setup", "call", "teardown")
            or report.when in phases
            or report.outcome != "passed"
            or getattr(report, "wasxfail", None) is not None
        ):
            self.errors += 1
            return
        phases.add(report.when)
        if report.when == "call":
            self.calls.add(report.nodeid)

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        complete = (
            exitstatus == 0
            and self.errors == 0
            and bool(self.reports)
            and set(self.files) == set(TEST_FILES)
            and all(phases == {"setup", "call", "teardown"} for phases in self.reports.values())
        )
        _write_receipt(
            self.receipt_path,
            {
                "status": "passed" if complete else "failed",
                "project_ref": self.expected_ref,
                "files": self.files,
                "collected": len(self.reports),
                "passed": len(self.calls),
                "errors": self.errors + (0 if complete else 1),
            },
        )


def _worker(settings_root: Path, expected_project_ref: str, artifacts: Path) -> int:
    try:
        isolated = _isolated_root(settings_root, expected_project_ref)
        for purpose in ("admin", "transformer"):
            _settings(isolated, purpose, expected_project_ref)
        artifacts = _contained(isolated, artifacts)
        if not artifacts.is_dir() or artifacts.parent != _contained(
            isolated, isolated / ".artifacts" / "reconstruction-acceptance"
        ):
            raise ValueError
        basetemp = artifacts / "basetemp"
        if basetemp.exists() or basetemp.is_symlink():
            raise ValueError
        plugin = _AcceptancePlugin(isolated, expected_project_ref, artifacts / "receipt.json")
        return int(
            pytest.main(
                [
                    "--rootdir",
                    str(ROOT),
                    "--noconftest",
                    "--basetemp",
                    str(basetemp),
                    "-o",
                    "addopts=-q",
                    "-p",
                    "no:cacheprovider",
                    "--capture=no",
                    *(str(ROOT / "tests" / name) for name in TEST_FILES),
                ],
                plugins=[plugin],
            )
        )
    except KeyboardInterrupt:
        return 130
    except Exception:
        return 1


def run_reconstruction_acceptance(
    *, settings_root: Path, expected_project_ref: str
) -> dict[str, Any]:
    """Validate isolation, then launch only the fixed native worker; never retry."""
    try:
        isolated = _isolated_root(settings_root, expected_project_ref)
        for purpose in ("admin", "transformer"):
            _settings(isolated, purpose, expected_project_ref)
        if any(not (ROOT / "tests" / name).is_file() for name in TEST_FILES):
            raise ValueError
        artifacts = _contained(
            isolated,
            isolated / ".artifacts" / "reconstruction-acceptance" / uuid4().hex,
        )
        artifacts.mkdir(parents=True, exist_ok=False)
        receipt_path = artifacts / "receipt.json"
        _write_receipt(
            receipt_path,
            {
                "status": "incomplete",
                "project_ref": expected_project_ref,
                "files": {},
                "collected": 0,
                "passed": 0,
                "errors": 0,
            },
        )
        environment = {
            name: value
            for name, value in os.environ.items()
            if not name.upper().startswith(("WAREHOUSE_", "PG", "DBT_", "PYTEST_", "COMMERCE_"))
        }
        environment.update({name: "1" for name in OPT_IN_NAMES})
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                WORKER_BOOTSTRAP,
                str(ROOT),
                str(isolated),
                expected_project_ref,
                str(artifacts),
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ACCEPTANCE_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError
        return {**_verify_receipt(receipt_path, expected_project_ref), "artifacts": str(artifacts)}
    except KeyboardInterrupt:
        raise KeyboardInterrupt("Reconstruction acceptance interrupted; receipt retained") from None
    except Exception:
        raise ReconstructionAcceptanceError(FAILURE_MESSAGE) from None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run fixed isolated final checks", exit_on_error=False
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--settings-root", type=Path)
    parser.add_argument("--expected-project-ref")
    try:
        args, unknown = parser.parse_known_args()
        if (
            not args.run
            or unknown
            or args.settings_root is None
            or args.expected_project_ref is None
        ):
            raise ValueError
        receipt = run_reconstruction_acceptance(
            settings_root=args.settings_root,
            expected_project_ref=args.expected_project_ref,
        )
        print(json.dumps(receipt, indent=2))
        return 0
    except KeyboardInterrupt:
        print("Reconstruction acceptance interrupted; receipt retained", file=sys.stderr)
        return 130
    except Exception:
        print(FAILURE_MESSAGE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
