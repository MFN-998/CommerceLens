"""Release local batch locks without deleting project-generated resources."""

from pathlib import Path
from uuid import uuid4


def release_lock(lock: Path) -> Path:
    """Move this run's lock to a fresh sibling; retain its contents and evidence.

    An interrupted active lock remains at its original name and still fails closed.
    No tree traversal, cleanup, replacement of earlier evidence or source move occurs.
    """
    if (
        lock.parent.name != ".artifacts"
        or lock.name not in {"olist-acquisition.lock", "olist-validation.lock"}
        or lock.is_symlink()
        or not lock.is_dir()
    ):
        raise ValueError("Cannot release an unexpected batch lock; inspect retained state")
    retained = lock.with_name(f"{lock.name}.released-{uuid4().hex}")
    if retained.exists() or retained.is_symlink():
        raise ValueError("Refusing to replace retained lock evidence")
    lock.rename(retained)
    return retained
