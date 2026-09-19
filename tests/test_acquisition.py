"""Synthetic integrity tests; no network access or real dataset is required."""

import json
import shutil
from pathlib import Path

import pytest

from src.ingestion.olist import (
    DATASET_HANDLE,
    EXPECTED_FILES,
    AcquisitionError,
    acquire,
    sha256_file,
    verify_raw,
)


@pytest.fixture
def acquisition_paths(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    source = tmp_path / "source"
    project.mkdir()
    source.mkdir()
    for index, name in enumerate(EXPECTED_FILES):
        (source / name).write_bytes(f'column,value\r\n{index},"a,b"\r\n'.encode())
    return project, source


def test_acquire_preserves_bytes_and_is_idempotent(acquisition_paths):
    project, source = acquisition_paths
    manifest = acquire(project, source)
    manifest_path = project / "data" / "source-manifest.json"
    saved_provenance = manifest_path.read_bytes()
    assert manifest["dataset_handle"] == DATASET_HANDLE
    assert manifest["dataset_version"] == 2
    assert set(manifest["files"]) == set(EXPECTED_FILES)
    for name in EXPECTED_FILES:
        original = source / name
        snapshot = project / "data" / "raw" / "olist-v2" / name
        assert snapshot.read_bytes() == original.read_bytes()
        assert manifest["files"][name] == {
            "sha256": sha256_file(original),
            "bytes": original.stat().st_size,
        }
    assert acquire(project, source) == manifest
    assert acquire(project) == manifest
    assert verify_raw(project) == manifest
    assert manifest_path.read_bytes() == saved_provenance
    assert list((project / ".artifacts").iterdir()) == []


def test_tampered_raw_is_detected_and_never_repaired_silently(acquisition_paths):
    project, source = acquisition_paths
    acquire(project, source)
    snapshot = project / "data" / "raw" / "olist-v2" / EXPECTED_FILES[0]
    original = snapshot.read_bytes()
    # Preserve length to exercise hash checking independently of byte-count checking.
    tampered = b"X" + original[1:]
    snapshot.write_bytes(tampered)
    manifest_path = project / "data" / "source-manifest.json"
    before = manifest_path.read_bytes()
    with pytest.raises(AcquisitionError, match="integrity mismatch"):
        verify_raw(project)
    with pytest.raises(AcquisitionError, match="integrity mismatch"):
        acquire(project, source)
    assert snapshot.read_bytes() == tampered
    assert manifest_path.read_bytes() == before


@pytest.mark.parametrize("invalid_inventory", ["missing", "unexpected", "directory"])
def test_invalid_source_inventory_leaves_no_snapshot(acquisition_paths, invalid_inventory):
    project, source = acquisition_paths
    if invalid_inventory == "missing":
        (source / EXPECTED_FILES[0]).unlink()
    elif invalid_inventory == "unexpected":
        (source / "unlisted.csv").write_bytes(b"unexpected")
    else:
        (source / EXPECTED_FILES[0]).unlink()
        (source / EXPECTED_FILES[0]).mkdir()
    with pytest.raises(AcquisitionError, match="exactly nine|regular, non-symlink"):
        acquire(project, source)
    assert not (project / "data" / "raw" / "olist-v2").exists()
    assert not (project / "data" / "source-manifest.json").exists()
    assert list((project / ".artifacts").iterdir()) == []


@pytest.mark.parametrize("inventory_change", ["missing", "unexpected"])
def test_verify_rejects_changed_raw_inventory(acquisition_paths, inventory_change):
    project, source = acquisition_paths
    acquire(project, source)
    raw = project / "data" / "raw" / "olist-v2"
    if inventory_change == "missing":
        (raw / EXPECTED_FILES[0]).unlink()
    else:
        (raw / "unlisted.txt").write_bytes(b"unexpected")
    with pytest.raises(AcquisitionError, match="exactly nine"):
        verify_raw(project)


def test_restore_requires_exact_manifest_hashes_and_preserves_provenance(
    acquisition_paths,
):
    project, source = acquisition_paths
    original = acquire(project, source)
    manifest_path = project / "data" / "source-manifest.json"
    saved_provenance = manifest_path.read_bytes()
    raw = project / "data" / "raw" / "olist-v2"
    assert raw.resolve().is_relative_to(project.resolve())
    shutil.rmtree(raw)
    original_bytes = (source / EXPECTED_FILES[0]).read_bytes()
    (source / EXPECTED_FILES[0]).write_bytes(b"conflicting bytes")
    with pytest.raises(AcquisitionError, match="integrity mismatch"):
        acquire(project, source)
    assert not raw.exists()
    assert manifest_path.read_bytes() == saved_provenance
    (source / EXPECTED_FILES[0]).write_bytes(original_bytes)
    assert acquire(project, source) == original
    assert verify_raw(project) == original
    assert manifest_path.read_bytes() == saved_provenance


def test_conflicting_manifest_is_not_replaced(acquisition_paths):
    project, source = acquisition_paths
    acquire(project, source)
    manifest_path = project / "data" / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset_version"] = 3
    manifest_path.write_text(json.dumps(manifest))
    before = manifest_path.read_bytes()
    with pytest.raises(AcquisitionError, match="conflicting dataset_version"):
        acquire(project, source)
    assert manifest_path.read_bytes() == before


def test_existing_raw_without_manifest_is_not_adopted(acquisition_paths):
    project, source = acquisition_paths
    raw = project / "data" / "raw" / "olist-v2"
    raw.parent.mkdir(parents=True)
    shutil.copytree(source, raw)
    with pytest.raises(AcquisitionError, match="manifest is missing"):
        acquire(project, source)
    assert not (project / "data" / "source-manifest.json").exists()
    assert (raw / EXPECTED_FILES[0]).read_bytes() == (source / EXPECTED_FILES[0]).read_bytes()


def test_conflicting_explicit_source_cannot_replace_valid_snapshot(acquisition_paths):
    project, source = acquisition_paths
    manifest = acquire(project, source)
    (source / EXPECTED_FILES[0]).write_bytes(b"replacement")
    with pytest.raises(AcquisitionError, match="integrity mismatch"):
        acquire(project, source)
    assert verify_raw(project) == manifest


def test_kaggle_transport_marker_is_ignored_only_at_source(acquisition_paths):
    project, source = acquisition_paths
    marker = source / ".complete"
    marker.mkdir()
    (marker / "transport-marker").write_bytes(b"download complete")
    manifest = acquire(project, source)
    raw = project / "data" / "raw" / "olist-v2"
    assert set(path.name for path in raw.iterdir()) == set(EXPECTED_FILES)
    assert acquire(project, source) == manifest
    (raw / ".complete").mkdir()
    with pytest.raises(AcquisitionError, match="unexpected: .complete"):
        verify_raw(project)


def test_transport_marker_name_does_not_allow_arbitrary_files(acquisition_paths):
    project, source = acquisition_paths
    (source / ".complete").write_bytes(b"not a KaggleHub directory")
    with pytest.raises(AcquisitionError, match="unexpected: .complete"):
        acquire(project, source)
