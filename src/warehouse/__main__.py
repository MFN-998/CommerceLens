"""Run with: uv run --locked --group warehouse python -m src.warehouse inspect."""

import argparse
import json
import sys

import psycopg
from pydantic import ValidationError

from src.warehouse.config import connect, load_settings
from src.warehouse.credentials import ProvisioningError, provision_loader
from src.warehouse.migrations import (
    MigrationError,
    apply_migrations,
    inspect_database,
    read_migrations,
    verify_privileges,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private development warehouse administration")
    parser.add_argument(
        "command", choices=["inspect", "migrate", "verify", "rehearse", "provision-loader"]
    )
    args = parser.parse_args()
    try:
        settings = load_settings()
        if args.command == "provision-loader":
            print(json.dumps(provision_loader(settings), indent=2))
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
    except ProvisioningError as error:
        # Provisioning exposes only fixed recovery instructions, never driver detail.
        print(str(error), file=sys.stderr)
    except (MigrationError, ValueError, OSError):
        print(
            "Warehouse configuration or migration validation failed; review target and history.",
            file=sys.stderr,
        )
    except psycopg.Error as error:
        # PostgreSQL error detail can contain SQL, source values, or connection secrets.
        code = error.sqlstate or "connection"
        print(
            f"Warehouse operation failed ({type(error).__name__}, {code}); no error detail logged.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
