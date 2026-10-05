"""Preserved locks must release concurrency gates without deleting evidence."""

from pathlib import Path

import pytest

from src.retention import release_lock


def test_release_preserves_contents_and_does_not_replace_previous_evidence(tmp_path):
    artifacts = tmp_path / ".artifacts"
    artifacts.mkdir()
    released = []
    for text in ("first receipt", "second receipt"):
        lock = artifacts / "olist-validation.lock"
        lock.mkdir()
        (lock / "receipt.txt").write_text(text)
        retained = release_lock(lock)
        assert not lock.exists()
        assert retained.parent == artifacts
        assert retained.name.startswith("olist-validation.lock.released-")
        assert (retained / "receipt.txt").read_text() == text
        released.append(retained)
    assert released[0] != released[1]
    assert (released[0] / "receipt.txt").read_text() == "first receipt"


@pytest.mark.parametrize(
    "parent,name", [("data", "olist-validation.lock"), (".artifacts", "source")]
)
def test_release_refuses_unexpected_resource_and_preserves_it(tmp_path, parent, name):
    lock = tmp_path / parent / name
    lock.mkdir(parents=True)
    (lock / "keep.txt").write_text("retained")
    with pytest.raises(ValueError, match="unexpected batch lock"):
        release_lock(lock)
    assert (lock / "keep.txt").read_text() == "retained"


def test_failed_release_leaves_active_lock_and_contents(tmp_path, monkeypatch):
    lock = tmp_path / ".artifacts" / "olist-acquisition.lock"
    lock.mkdir(parents=True)
    (lock / "keep.txt").write_text("retained")

    def fail(*args):
        raise OSError("simulated move failure")

    monkeypatch.setattr(Path, "rename", fail)
    with pytest.raises(OSError, match="simulated move failure"):
        release_lock(lock)
    assert (lock / "keep.txt").read_text() == "retained"
