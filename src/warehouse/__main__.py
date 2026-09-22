"""Run with: uv run --locked --group warehouse python -m src.warehouse inspect."""

import argparse
import json
import sys

import psycopg
from pydantic import ValidationError

from src.warehouse.config import ROOT, connect, load_settings
from src.warehouse.credentials import ProvisioningError, provision_loader, provision_transformer
from src.warehouse.dbt_runner import DbtCommand, DbtError, run_dbt
from src.warehouse.loading import LoadError, load_source
from src.warehouse.migrations import (
    MigrationError,
    apply_migrations,
    inspect_database,
    read_migrations,
    verify_privileges,
)
from src.warehouse.source import prepare_source


def main() -> int:
    parser = argparse.ArgumentParser(description="Private development warehouse administration")
    parser.add_argument(
        "command",
        choices=[
            "inspect",
            "migrate",
            "verify",
            "rehearse",
            "provision-loader",
            "load",
            "provision-transformer",
            "dbt-parse",
            "dbt-debug",
        ],
    )
    args = parser.parse_args()
    try:
        if args.command in ("dbt-parse", "dbt-debug"):
            dbt_command: DbtCommand = "parse" if args.command == "dbt-parse" else "debug"
            print(json.dumps(run_dbt(dbt_command), indent=2))
            return 0
        if args.command == "load":
            settings = load_settings(purpose="loader")
            print(
                "Verifying all local source files before connecting.", file=sys.stderr, flush=True
            )
            plan = prepare_source(ROOT)
            with connect(settings) as connection:
                load_result = load_source(
                    connection,
                    ROOT,
                    plan,
                    progress=lambda message: print(message, file=sys.stderr, flush=True),
                )
            # Report success only after the transaction and connection exit cleanly.
            print(json.dumps({"project_ref": settings.project_ref, **load_result}, indent=2))
            return 0
        settings = load_settings()
        if args.command == "provision-loader":
            print(json.dumps(provision_loader(settings), indent=2))
            return 0
        if args.command == "provision-transformer":
            print(json.dumps(provision_transformer(settings), indent=2))
            return 0
        migrations = read_migrations()
        with connect(settings) as connection:
            result: dict[str, object] = {
                "command": args.command,
                "project_ref": settings.project_ref,
            }
            if args.command == "migrate":
                result["applied"] = apply_migrations(connection, migrations)
            elif args.command == "verify":
                verify_privileges(connection)
                result["privilege_checks"] = "passed; fixtures rolled back"
            elif args.command == "rehearse":
                before = inspect_database(connection)
                if before["schemas"] or before["capability_roles"]:
                    raise MigrationError(
                        "Rehearse the first bootstrap only on an empty warehouse target"
                    )
                with connection.transaction(force_rollback=True):
                    apply_migrations(connection, migrations)
                    verify_privileges(connection)
                    if apply_migrations(connection, migrations):
                        raise MigrationError("Identical migration replay was not a no-op")
                after = inspect_database(connection)
                if any(
                    after[key] != before[key]
                    for key in ("schemas", "capability_roles", "default_acl_count")
                ):
                    raise MigrationError(
                        "Bootstrap rollback left warehouse objects or roles behind"
                    )
                result["rehearsal"] = (
                    "bootstrap, permission checks, and repeat migration rolled back"
                )
            result["database"] = inspect_database(connection)
            print(json.dumps(result, indent=2))
        return 0
    except ValidationError as error:
        fields = sorted(
            {str(item["loc"][0]) if item["loc"] else "target" for item in error.errors()}
        )
        print("Invalid warehouse configuration fields: " + ", ".join(fields), file=sys.stderr)
    except (ProvisioningError, LoadError, DbtError) as error:
        # These errors expose fixed recovery instructions, never driver or row detail.
        print(str(error), file=sys.stderr)
    except (MigrationError, ValueError, OSError):
        print(
            "Warehouse validation failed; review configuration, source provenance, and history.",
            file=sys.stderr,
        )
    except psycopg.Error as error:
        # PostgreSQL error detail can contain SQL, source values, or connection secrets.
        code = error.sqlstate or "connection"
        print(
            f"Warehouse operation failed ({type(error).__name__}, {code}); no error detail logged.",
            file=sys.stderr,
        )
    except KeyboardInterrupt:
        print(
            "Warehouse operation interrupted; verify committed state before resuming.",
            file=sys.stderr,
        )
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
