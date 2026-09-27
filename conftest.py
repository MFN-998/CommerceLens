"""Retain fixture files: cleanup requires explicit owner approval."""

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """Avoid pytest's deleting basetemp/numbered-directory implementation."""
    path = request.config.rootpath / ".artifacts" / "pytest" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path
