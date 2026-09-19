"""Reproducible Phase 2 inventory, validation, local staging, and reporting."""

import argparse
import csv
import json
import os
import platform
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from src.cleaning.staging import read_source, standardize
from src.ingestion.olist import DEFAULT_PROJECT_ROOT, sha256_file, verify_raw
from src.validation.contracts import TABLES
from src.validation.profile import (
    check,
    contextual_checks,
    join_diagnostics,
    relationship_checks,
    table_profile,
    validate_frame,
)

STAGING_FORMAT_VERSION = 1


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_json(path: Path, value: dict) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def stage_frames(project_root: Path, frames: dict[str, pd.DataFrame]) -> dict:
    """Publish a complete new snapshot or verify identical existing output; never replace it."""
    interim = project_root / "data" / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    destination = interim / "olist-v2-v1"
    manifest = {
        "staging_format_version": STAGING_FORMAT_VERSION,
        "source_manifest_sha256": sha256_file(project_root / "data" / "source-manifest.json"),
        "pandas": version("pandas"),
        "pyarrow": version("pyarrow"),
        "files": {},
    }
    with tempfile.TemporaryDirectory(prefix=".olist-staging-", dir=interim) as temporary:
        prepared = Path(temporary) / "snapshot"
        prepared.mkdir()
        for table, frame in frames.items():
            path = prepared / f"{table}.parquet"
            frame.to_parquet(path, index=False, engine="pyarrow", compression="zstd")
            restored = pd.read_parquet(path)
            pd.testing.assert_frame_equal(frame, restored, check_dtype=True)
            manifest["files"][path.name] = {
                "sha256": sha256_file(path),
                "rows": len(frame),
            }
        write_json(prepared / "_manifest.json", manifest)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError("Staging destination must be a real directory.")
            expected = set(manifest["files"]) | {"_manifest.json"}
            if {p.name for p in destination.iterdir()} != expected:
                raise ValueError("Existing staging snapshot has unexpected or missing files.")
            for name in expected:
                path = destination / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"Staging file is not a regular file: {name}")
                if sha256_file(path) != sha256_file(prepared / name):
                    raise ValueError(
                        f"Staging differs: {name}; refusing overwrite. Investigate first."
                    )
            action = "verified_existing"
        else:
            prepared.rename(destination)
            action = "created"
    return {
        "promoted": True,
        "path": destination.relative_to(project_root).as_posix(),
        "action": action,
    }


def report_markdown(report: dict) -> str:
    review_keys = report["tables"].get("order_reviews", {}).get("keys", {})
    composite = review_keys.get("review_id, order_id")
    if composite is None:
        review_note = "- Review key validation is unavailable; inspect the blocking checks."
    else:
        valid = not (composite["rows_in_duplicate_keys"] or composite["null_key_rows"])
        outcome = "passed" if valid else "failed"
        individual_counts = ", ".join(
            f"{key}: {review_keys[key]['rows_in_duplicate_keys']:,} rows in repeated keys"
            for key in ("review_id", "order_id")
            if key in review_keys
        )
        review_note = (
            f"- Observed (review_id, order_id) uniqueness/null checks {outcome}. "
            f"Individual-key observations: {individual_counts}. All review records are retained."
        )
    lines = [
        "# Olist Phase 2 data-quality report",
        "",
        f"Status: **{report['status']}**. Generated: {report['generated_at_utc']}.",
        "",
        "Source: [Olist on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), "
        "version 2; historical anonymized data, not a live business feed.",
        "",
        "Raw bytes are preserved. Empty CSV fields become null; identifiers and free text remain "
        "strings. The UTF-8 BOM is handled during reading. "
        "No rows are dropped, imputed, or deduplicated.",
        "",
        f"Positive blocking checks: **{report['error_checks']}**. "
        f"Positive warning checks: **{report['warning_checks']}**. Counts can overlap.",
        "",
        f"Staging: `{report['staging'].get('path')}`; "
        f"action: `{report['staging'].get('action', 'not_promoted')}`.",
        "",
        "## Inventory and observed grains",
        "",
        "| Table | Rows | Columns | Exact excess duplicates | Enforced source key |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, value in report["tables"].items():
        key = ", ".join(value["confirmed_key"]) or "No natural key; source row only"
        lines.append(
            f"| {name} | {value['rows']:,} | {value['source_columns']} | "
            f"{value['duplicate_rows_excluding_first']:,} | {key} |"
        )
    lines += [
        "",
        "## Observations requiring attention",
        "",
        "Warnings are preserved source limitations, not repaired records. "
        "They require eligibility or aggregation decisions before downstream analytics.",
        "",
        "| Severity | Table | Check | Count | Unit | Interpretation |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in report["checks"]:
        if item["count"]:
            detail = item["detail"].replace("|", "/").replace("\n", " ")
            lines.append(
                f"| {item['severity']} | {item['table']} | {item['name']} | "
                f"{item['count']:,} | {item['unit']} | {detail} |"
            )
    lines += [
        "",
        "## Missing lifecycle dates by source order status",
        "",
        "| Status | Orders | Missing approval | Missing carrier handoff | Missing delivery |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for status, values in report.get("orders_by_status", {}).items():
        missing = values["missing_events"]
        lines.append(
            f"| {status} | {values['orders']:,} | {missing['order_approved_at']:,} | "
            f"{missing['order_delivered_carrier_date']:,} | "
            f"{missing['order_delivered_customer_date']:,} |"
        )
    if "join_diagnostics" in report:
        join = report["join_diagnostics"]
        lines += [
            "",
            "## Join-grain warning",
            "",
            f"{join['orders_with_multiple_items_and_payments']:,} orders have both multiple "
            "items and multiple payment components. "
            f"An item/payment inner join on order_id produces "
            f"{join['inner_join_rows_items_to_payments_on_order']:,} rows.",
            "",
            join["interpretation"],
        ]
    lines += [
        "",
        "## Interpretation and limitations",
        "",
        "- Optional review text is measured in the dictionary, not treated as an error.",
        "- Missing event timestamps are contextual: non-delivered orders may not have "
        "delivery dates; delivered orders missing them are explicitly flagged.",
        review_note,
        "- Customer identity across orders uses customer_unique_id, whereas the source "
        "order relationship uses customer_id.",
        "- Geography needs a documented unique ZIP mapping before joins. The broad "
        "Brazil coordinate box is an exploratory screen, not a geographic boundary test.",
        "- All source timestamps are timezone-naive because the source does not declare "
        "a timezone. No UTC conversion is invented.",
        "- Monetary amounts remain source numeric values; this phase defines no GMV, "
        "revenue, profit, or payment-reconciliation business metric.",
        "- FAIL blocks promotion. PASS_WITH_WARNINGS permits the faithful local staging "
        "snapshot, not unrestricted analytical use of all rows.",
        "",
        "The [JSON report](data-quality-report.json) includes checks, hashes, column "
        "missingness/ranges, candidate-key counts, and categorical domains. "
        "See the [initial dictionary](data_dictionary/initial.md) for column meanings.",
        "",
    ]
    return "\n".join(lines)


def dictionary_markdown(report: dict) -> str:
    lines = [
        "# Initial Olist source and staging dictionary",
        "",
        "Observed against pinned Olist version 2. These are source contracts, not "
        "the Phase 3 warehouse design. All source names, including `lenght`, are preserved.",
        "",
        "Every staging table adds `_source_row` (nullable integer dtype, no null values): "
        "the 1-based CSV data-record ordinal, excluding the header. It is not a physical "
        "line number because review text can contain line breaks.",
        "",
    ]
    for name, table in report["tables"].items():
        lines += [
            f"## {name}",
            "",
            table["grain"],
            "",
            f"Source: `{table['filename']}` — {table['rows']:,} records.",
            "",
            "| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
        for column, value in table["columns"].items():
            lines.append(
                f"| {column} | {value['dtype']} | {value['nullable_by_contract']} | "
                f"{value['nulls']:,} | {value['distinct_non_null']:,} | {value['description']} |"
            )
        lines += ["", "Observed keys:", ""]
        for key, value in table["keys"].items():
            lines.append(
                f"- `{key}`: {value['distinct_keys']:,} distinct keys, "
                f"{value['rows_in_duplicate_keys']:,} rows in repeated keys, "
                f"{value['null_key_rows']:,} null-key rows; enforced: {value['enforced']}."
            )
        lines.append("")
    return "\n".join(lines)


def run(project_root: Path = DEFAULT_PROJECT_ROOT) -> dict:
    root = Path(project_root).resolve()
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ("pandas", "pandera", "pyarrow")},
        "tables": {},
        "checks": [],
        "staging": {"promoted": False, "path": None},
    }
    frames = {}
    try:
        manifest = verify_raw(root)
        report["source"] = manifest
        for table, spec in TABLES.items():
            try:
                raw = read_source(root / "data" / "raw" / "olist-v2" / spec.filename, table)
                frame, failures = standardize(raw, table)
                frames[table] = frame
                report["tables"][table] = table_profile(
                    table, raw, frame, manifest["files"][spec.filename]
                )
                for column, count in failures.items():
                    report["checks"].append(
                        check(
                            f"parse:{column}",
                            table,
                            "error",
                            count,
                            "Non-empty values that cannot be represented in the declared type.",
                        )
                    )
                report["checks"].extend(validate_frame(table, frame))
            except (OSError, ValueError, TypeError, csv.Error) as exc:
                frames.pop(table, None)
                report["checks"].append(check("source_read", table, "error", 1, str(exc), "files"))
        report["checks"].extend(relationship_checks(frames))
        if set(frames) == set(TABLES):
            contextual, status_profile = contextual_checks(frames)
            report["checks"].extend(contextual)
            report["orders_by_status"] = status_profile
            report["join_diagnostics"] = join_diagnostics(frames)
        # Catch any raw change during processing before considering staging promotion.
        if verify_raw(root) != manifest:
            raise ValueError("Source provenance changed during processing.")
        if not any(c["severity"] == "error" and c["count"] for c in report["checks"]):
            report["staging"] = stage_frames(root, frames)
    except (OSError, ValueError, TypeError, AssertionError) as exc:
        report["checks"].append(
            check("integrity_or_staging", "snapshot", "error", 1, str(exc), "snapshots")
        )
    report["error_checks"] = sum(
        c["severity"] == "error" and c["count"] > 0 for c in report["checks"]
    )
    report["warning_checks"] = sum(
        c["severity"] == "warning" and c["count"] > 0 for c in report["checks"]
    )
    report["status"] = (
        "FAIL"
        if report["error_checks"]
        else ("PASS_WITH_WARNINGS" if report["warning_checks"] else "PASS")
    )
    write_json(root / "docs" / "data-quality-report.json", report)
    write_text(root / "docs" / "data-quality-report.md", report_markdown(report))
    write_text(root / "docs" / "data_dictionary" / "initial.md", dictionary_markdown(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    args = parser.parse_args()
    report = run(args.project_root)
    print(
        json.dumps(
            {key: report[key] for key in ("status", "error_checks", "warning_checks", "staging")}
        )
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
