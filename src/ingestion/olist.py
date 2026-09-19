"""Acquire and verify the pinned Olist release without changing source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

DATASET_HANDLE = "olistbr/brazilian-ecommerce/versions/2"
SOURCE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
LICENSE = {
    "label": "CC BY-NC-SA 4.0",
    "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
}
EXPECTED_FILES = (
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AcquisitionError(ValueError):
    """The source or existing snapshot failed an integrity requirement."""


def sha256_file(path: Path) -> str:
    """Hash file bytes in bounded memory without interpreting their contents."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _file_records(directory: Path, *, allow_transport_marker: bool = False) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise AcquisitionError("The source snapshot must be a real directory.")
    actual = {entry.name for entry in directory.iterdir()}
    marker = directory / ".complete"
    if (
        allow_transport_marker
        and ".complete" in actual
        and marker.is_dir()
        and not marker.is_symlink()
    ):
        actual.remove(".complete")
    expected = set(EXPECTED_FILES)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise AcquisitionError(
            f"Expected exactly nine Olist CSV files; missing: {missing}; unexpected: {unexpected}."
        )
    records = {}
    for name in EXPECTED_FILES:
        path = directory / name
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise AcquisitionError(f"Source file must be a regular, non-symlink file: {name}.")
        records[name] = {"sha256": sha256_file(path), "bytes": metadata.st_size}
    return records


def _read_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise AcquisitionError("The source manifest is missing or is not a regular file.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise AcquisitionError("The source manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict):
        raise AcquisitionError("The source manifest must contain a JSON object.")
    expected_metadata = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "dataset_handle": DATASET_HANDLE,
        "dataset_version": 2,
        "license": LICENSE,
    }
    for key, expected in expected_metadata.items():
        if manifest.get(key) != expected:
            raise AcquisitionError(f"The source manifest has conflicting {key}.")
    try:
        acquired = datetime.fromisoformat(manifest["acquired_at_utc"])
        if acquired.utcoffset() != UTC.utcoffset(acquired):
            raise ValueError("Expected UTC.")
    except (KeyError, TypeError, ValueError) as exc:
        raise AcquisitionError(
            "The source manifest requires a valid UTC acquisition time."
        ) from exc
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(EXPECTED_FILES):
        raise AcquisitionError("The source manifest must list exactly the nine Olist CSV files.")
    for name, record in files.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"sha256", "bytes"}
            or not isinstance(record["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
            or type(record["bytes"]) is not int
            or record["bytes"] < 0
        ):
            raise AcquisitionError(f"The source manifest has an invalid file record: {name}.")
    return manifest


def _require_matching(actual: dict, expected: dict) -> None:
    mismatched = [name for name in EXPECTED_FILES if actual[name] != expected[name]]
    if mismatched:
        raise AcquisitionError("Source integrity mismatch: " + ", ".join(mismatched) + ".")


def verify_raw(project_root: Path = DEFAULT_PROJECT_ROOT) -> dict:
    """Verify the exact file inventory, lengths and SHA-256 hashes; return provenance."""
    root = Path(project_root).resolve()
    manifest = _read_manifest(root / "data" / "source-manifest.json")
    actual = _file_records(root / "data" / "raw" / "olist-v2")
    _require_matching(actual, manifest["files"])
    return manifest


def _prepare_directory(path: Path) -> None:
    if path.is_symlink() or (_exists(path) and not path.is_dir()):
        raise AcquisitionError(f"Expected a real directory: {path.name}.")
    path.mkdir(exist_ok=True)


def _cleanup_temporary(path: Path, artifacts: Path) -> None:
    resolved = path.resolve()
    if (
        path.is_symlink()
        or not resolved.is_relative_to(artifacts.resolve())
        or resolved == artifacts.resolve()
        or not path.name.startswith("olist-acquisition-")
    ):
        raise AcquisitionError("Refusing cleanup outside the acquisition temporary directory.")
    shutil.rmtree(path)


def _download(destination: Path) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise AcquisitionError(
            "Install the data dependency group before downloading Olist."
        ) from exc
    try:
        return Path(kagglehub.dataset_download(DATASET_HANDLE, output_dir=str(destination)))
    except Exception as exc:
        # Client exceptions can include authenticated URLs. Keep the public error concise.
        raise AcquisitionError(
            "Kaggle download failed; check connectivity and Kaggle access."
        ) from exc


def acquire(project_root: Path = DEFAULT_PROJECT_ROOT, source_dir: Path | None = None) -> dict:
    """Acquire version 2 once, or verify/restore a snapshot against recorded provenance.

    A supplied source directory supports offline acquisition. Both downloaded and
    supplied sources are checked and copied byte-for-byte before promotion. An
    existing manifest is never rewritten, including when restoring missing raw data.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise AcquisitionError("The project root must already exist.")
    data = root / "data"
    raw_parent = data / "raw"
    raw = raw_parent / "olist-v2"
    manifest_path = data / "source-manifest.json"
    artifacts = root / ".artifacts"
    _prepare_directory(artifacts)
    lock = artifacts / "olist-acquisition.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise AcquisitionError(
            "Another acquisition is active; acquisition lock already exists."
        ) from exc
    temporary = None
    try:
        if _exists(raw):
            manifest = verify_raw(root)
            if source_dir is not None:
                _require_matching(
                    _file_records(Path(source_dir), allow_transport_marker=True),
                    manifest["files"],
                )
            return manifest
        existing_manifest = _read_manifest(manifest_path) if _exists(manifest_path) else None
        _prepare_directory(data)
        _prepare_directory(raw_parent)
        temporary = Path(tempfile.mkdtemp(prefix="olist-acquisition-", dir=artifacts))
        source = Path(source_dir) if source_dir is not None else _download(temporary / "download")
        original_records = _file_records(source, allow_transport_marker=True)
        prepared = temporary / "snapshot"
        prepared.mkdir()
        for name in EXPECTED_FILES:
            shutil.copyfile(source / name, prepared / name, follow_symlinks=False)
        prepared_records = _file_records(prepared)
        _require_matching(prepared_records, original_records)
        if existing_manifest is not None:
            _require_matching(prepared_records, existing_manifest["files"])
            manifest = existing_manifest
            if _read_manifest(manifest_path) != manifest:
                raise AcquisitionError("The source manifest changed during acquisition.")
        else:
            manifest = {
                "schema_version": 1,
                "source_url": SOURCE_URL,
                "dataset_handle": DATASET_HANDLE,
                "dataset_version": 2,
                "acquired_at_utc": datetime.now(UTC).isoformat(),
                "license": dict(LICENSE),
                "files": prepared_records,
            }
        staged_manifest = temporary / "manifest.json"
        with staged_manifest.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(manifest, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if _exists(raw):
            raise AcquisitionError(
                "A raw snapshot appeared during acquisition; refusing overwrite."
            )
        prepared.rename(raw)
        if existing_manifest is None:
            try:
                # A hard link publishes complete bytes atomically and refuses any existing target.
                os.link(staged_manifest, manifest_path)
            except OSError:
                raw.rename(prepared)
                raise
        return manifest
    finally:
        try:
            if temporary is not None:
                _cleanup_temporary(temporary, artifacts)
        finally:
            lock.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument(
        "--source-dir", type=Path, help="Use an existing directory of nine source CSVs."
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check existing raw data without download.",
    )
    args = parser.parse_args()
    if args.verify and args.source_dir is not None:
        parser.error("--verify cannot be combined with --source-dir")
    try:
        manifest = (
            verify_raw(args.project_root)
            if args.verify
            else acquire(args.project_root, args.source_dir)
        )
    except (AcquisitionError, OSError) as exc:
        print(f"Acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(f"Verified {len(manifest['files'])} source files for {DATASET_HANDLE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
