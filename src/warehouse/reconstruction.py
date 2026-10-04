"""Run one reviewed reconstruction step against an isolated approved test target.

This does not create a project, authorize a target, automate a pipeline or retry.
Failures may retain committed objects or private files; reconcile before resuming.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from src.warehouse.access import grant_mart_reader
from src.warehouse.config import (
    PURPOSE_FILES,
    PURPOSE_USERS,
    ROOT,
    WarehousePurpose,
    WarehouseSettings,
    connect,
    load_settings,
)
from src.warehouse.credentials import (
    protect_credential_file,
    provision_loader,
    provision_transformer,
)
from src.warehouse.dbt_reconstruction import PROTECTED_PROJECT_REF, _contained, run_dbt_graph
from src.warehouse.loading import load_source
from src.warehouse.migrations import (
    apply_migrations,
    inspect_database,
    read_migrations,
    verify_privileges,
)
from src.warehouse.source import prepare_source

STEP_PURPOSES: dict[str, WarehousePurpose] = {
    "inspect": "admin",
    "migrate": "admin",
    "verify": "admin",
    "provision-loader": "admin",
    "provision-transformer": "admin",
    "load": "loader",
    "grant-mart-reader": "transformer",
    "dbt-build-graph": "transformer",
    "dbt-test-graph": "transformer",
}
FAILURE_MESSAGE = (
    "Reconstruction step failed; verify target and committed state before retrying; "
    "no detail logged"
)
INTERRUPTION_MESSAGE = "Reconstruction interrupted; verify committed state before resuming"


class ReconstructionError(ValueError):
    """A fixed, secret-safe reconstruction failure."""


def _isolated_root(settings_root: Path, expected_project_ref: str) -> Path:
    if (
        not isinstance(settings_root, Path)
        or not isinstance(expected_project_ref, str)
        or not re.fullmatch(r"[a-z]{20}", expected_project_ref)
        or expected_project_ref == PROTECTED_PROJECT_REF
        or any(name.upper().startswith(("WAREHOUSE_", "PG")) for name in os.environ)
    ):
        raise ValueError
    isolated = settings_root.resolve(strict=True)
    repo = ROOT.resolve()
    if not isolated.is_dir() or isolated.is_relative_to(repo) or repo.is_relative_to(isolated):
        raise ValueError
    return isolated


def _settings(root: Path, purpose: WarehousePurpose, expected_ref: str) -> WarehouseSettings:
    private = root / PURPOSE_FILES[purpose]
    if private.is_symlink():
        raise ValueError
    private = _contained(root, private)
    if not private.is_file() or private.stat().st_nlink != 1:
        raise ValueError
    protect_credential_file(private)
    settings = load_settings(root, purpose=purpose)
    if (
        settings.purpose != purpose
        or settings.environment != "test"
        or settings.project_ref != expected_ref
        or settings.project_ref == PROTECTED_PROJECT_REF
    ):
        raise ValueError
    certificate = _contained(root, settings.certificate_path(root))
    if not certificate.is_file():
        raise ValueError
    # Existing connect() resolves relative certificates against its repository root.
    return settings.model_copy(update={"sslrootcert": certificate})


def run_reconstruction_step(
    step: str, *, settings_root: Path, expected_project_ref: str
) -> dict[str, object]:
    """Dispatch one fixed step silently; return a receipt only after clean helper exits."""
    try:
        if step not in STEP_PURPOSES:
            raise ValueError
        isolated = _isolated_root(settings_root, expected_project_ref)
        if step in ("provision-loader", "provision-transformer"):
            generated_purpose: WarehousePurpose = (
                "loader" if step == "provision-loader" else "transformer"
            )
            destination = isolated / PURPOSE_FILES[generated_purpose]
            _contained(isolated, destination)
            if destination.exists() or destination.is_symlink():
                raise ValueError
        settings = _settings(isolated, STEP_PURPOSES[step], expected_project_ref)
        result: dict[str, object]
        if step in ("dbt-build-graph", "dbt-test-graph"):
            graph_receipt = run_dbt_graph(
                "build" if step == "dbt-build-graph" else "test",
                settings_root=isolated,
                expected_project_ref=expected_project_ref,
            )
            artifact_path = _contained(isolated, Path(str(graph_receipt["artifacts"])))
            result = {
                "models": graph_receipt["models"],
                "tests": graph_receipt["tests"],
                "artifacts": str(artifact_path),
            }
        elif step in ("provision-loader", "provision-transformer"):
            provision = provision_loader if step == "provision-loader" else provision_transformer
            provision(settings, root=isolated)
            result = {
                "role": PURPOSE_USERS[generated_purpose],
                "credential_file": PURPOSE_FILES[generated_purpose],
            }
        else:
            plan = prepare_source(ROOT) if step == "load" else None
            migrations = (
                read_migrations(ROOT / "warehouse" / "migrations") if step == "migrate" else []
            )
            with connect(settings) as connection:
                if step == "load":
                    load_receipt = load_source(connection, ROOT, plan)
                    if load_receipt["status"] not in ("loaded", "verified_existing"):
                        raise ValueError
                    result = {
                        key: load_receipt[key]
                        for key in (
                            "status",
                            "rows",
                            "raw_bytes",
                            "database_bytes",
                        )
                    }
                elif step == "migrate":
                    result = {
                        "applied_migration_count": len(apply_migrations(connection, migrations))
                    }
                elif step == "verify":
                    verify_privileges(connection)
                    result = {"privilege_checks": "passed"}
                elif step == "grant-mart-reader":
                    grant_mart_reader(connection, root=ROOT)
                    result = {
                        "status": "granted",
                        "model": "marts.mart_order_components",
                        "capability": "SELECT",
                    }
                else:
                    metadata = inspect_database(connection)
                    schemas, roles = metadata["schemas"], metadata["capability_roles"]
                    if not isinstance(schemas, dict) or not isinstance(roles, list):
                        raise ValueError
                    result = {
                        key: metadata[key]
                        for key in (
                            "database_bytes",
                            "default_acl_count",
                            "tls_in_use",
                        )
                    }
                    result.update(
                        schema_count=len(schemas),
                        capability_role_count=len(roles),
                    )
        return {
            "step": step,
            "project_ref": expected_project_ref,
            "status": "passed",
            "result": result,
        }
    except KeyboardInterrupt:
        raise KeyboardInterrupt(INTERRUPTION_MESSAGE) from None
    except Exception:
        # Helper/configuration/driver errors can contain credentials or source values.
        raise ReconstructionError(FAILURE_MESSAGE) from None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one isolated reconstruction step", exit_on_error=False
    )
    parser.add_argument("step", nargs="?", help="One of: " + ", ".join(STEP_PURPOSES))
    parser.add_argument("--settings-root", type=Path)
    parser.add_argument("--expected-project-ref")
    try:
        args, unknown = parser.parse_known_args()
        if (
            unknown
            or args.step is None
            or args.settings_root is None
            or args.expected_project_ref is None
        ):
            raise ReconstructionError(FAILURE_MESSAGE)
        receipt = run_reconstruction_step(
            args.step,
            settings_root=args.settings_root,
            expected_project_ref=args.expected_project_ref,
        )
        print(json.dumps(receipt, indent=2))
        return 0
    except KeyboardInterrupt:
        print(INTERRUPTION_MESSAGE, file=sys.stderr)
        return 130
    except Exception:
        print(FAILURE_MESSAGE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
