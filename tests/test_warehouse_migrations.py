"""Offline checks for migration tampering, ordering, and cross-platform reproducibility."""

from pathlib import Path

import pytest

from src.warehouse.migrations import MigrationError, pending_migrations, read_migrations


def test_replay_and_append_only_history(tmp_path: Path) -> None:
    (tmp_path / "0001_start.sql").write_text("SELECT 1;\n")
    (tmp_path / "0002_next.sql").write_text("SELECT 2;\n")
    migrations = read_migrations(tmp_path)
    first = migrations[0]
    assert pending_migrations(migrations, [(first.version, first.checksum)]) == migrations[1:]
    assert (
        pending_migrations(migrations, [(item.version, item.checksum) for item in migrations]) == []
    )


@pytest.mark.parametrize(
    "history", [[("0001", "tampered")], [("0002", "unknown")], [("0001", "a"), ("0002", "b")]]
)
def test_history_drift_rejected(tmp_path: Path, history: list[tuple[str, str]]) -> None:
    (tmp_path / "0001_start.sql").write_text("SELECT 1;\n")
    with pytest.raises(MigrationError):
        pending_migrations(read_migrations(tmp_path), history)


@pytest.mark.parametrize(
    "names", [[], ["0002_gap.sql"], ["0001_a.sql", "0001_b.sql"], ["unexpected.sql"]]
)
def test_invalid_migration_sequence_rejected(tmp_path: Path, names: list[str]) -> None:
    for name in names:
        (tmp_path / name).write_text("SELECT 1;\n")
    with pytest.raises(MigrationError):
        read_migrations(tmp_path)


def test_line_endings_do_not_change_checksum(tmp_path: Path) -> None:
    path = tmp_path / "0001_start.sql"
    path.write_bytes(b"SELECT 1;\r\n")
    first = read_migrations(tmp_path)[0]
    path.write_bytes(b"SELECT 1;\n")
    assert read_migrations(tmp_path)[0].checksum == first.checksum


def test_empty_migration_rejected(tmp_path: Path) -> None:
    (tmp_path / "0001_start.sql").write_text("   \n")
    with pytest.raises(MigrationError):
        read_migrations(tmp_path)
