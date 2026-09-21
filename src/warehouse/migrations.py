"""Ordered, checksummed SQL migrations with transactional recovery."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

from src.warehouse.config import ROOT

LOCK_ID = 4849330651682172499


class MigrationError(Exception):
    """An unsafe or inconsistent migration history was detected."""


@dataclass(frozen=True)
class Migration:
    version: str
    sql: str
    checksum: str


def read_migrations(directory: Path = ROOT / "warehouse/migrations") -> list[Migration]:
    migrations = []
    for number, path in enumerate(sorted(directory.glob("*.sql")), 1):
        match = re.fullmatch(r"(\d{4})_[a-z0-9_]+\.sql", path.name)
        if match is None or int(match[1]) != number:
            raise MigrationError("Migration files must be unique and sequential from 0001")
        # Canonical LF bytes keep checksums stable across Git's Windows newline handling.
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not content.strip():
            raise MigrationError("Empty migration file")
        migrations.append(
            Migration(match[1], content, hashlib.sha256(content.encode()).hexdigest())
        )
    if not migrations:
        raise MigrationError("No migration files found")
    return migrations


def pending_migrations(
    migrations: list[Migration], history: list[tuple[str, str]]
) -> list[Migration]:
    if len(history) > len(migrations):
        raise MigrationError("Database history contains unknown migrations")
    for migration, (version, checksum) in zip(migrations, history, strict=False):
        if migration.version != version or migration.checksum != checksum:
            raise MigrationError("Migration history differs from repository order or checksum")
    return migrations[len(history) :]


def apply_migrations(connection: psycopg.Connection, migrations: list[Migration]) -> list[str]:
    """Apply an entire pending batch atomically; a failure also rolls back its ledger rows."""
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        identity = connection.execute("SELECT session_user, current_database()").fetchone()
        if identity != ("postgres", "postgres"):
            raise MigrationError(
                "M2 bootstrap requires the reviewed postgres administration target"
            )
        exists = connection.execute("SELECT to_regclass('ops.schema_migrations')").fetchone()
        history = []
        if exists and exists[0] is not None:
            history = connection.execute(
                "SELECT version, checksum FROM ops.schema_migrations ORDER BY version"
            ).fetchall()
        pending = pending_migrations(migrations, history)
        for migration in pending:
            connection.execute(migration.sql, prepare=False)
            connection.execute("SET LOCAL ROLE commercelens_owner")
            connection.execute(
                "INSERT INTO ops.schema_migrations (version, checksum, applied_by) "
                "VALUES (%s, %s, session_user)",
                (migration.version, migration.checksum),
            )
            connection.execute("RESET ROLE")
        return [migration.version for migration in pending]


def verify_privileges(connection: psycopg.Connection) -> None:
    """Create fixtures and test real permissions, then discard all fixtures transactionally."""
    script = (ROOT / "warehouse/checks/privileges.sql").read_text(encoding="utf-8")
    with connection.transaction(force_rollback=True):
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        connection.execute(script, prepare=False)
    remaining = connection.execute(
        "SELECT count(*) FROM ("
        "SELECT relname AS name, relnamespace AS namespace FROM pg_class UNION ALL "
        "SELECT proname, pronamespace FROM pg_proc UNION ALL "
        "SELECT typname, typnamespace FROM pg_type) AS objects "
        "JOIN pg_namespace AS schemas ON schemas.oid = objects.namespace "
        "WHERE schemas.nspname IN ('ops','raw','staging','core','marts') "
        "AND strpos(objects.name, '__commercelens_') = 1"
    ).fetchone()
    if remaining != (0,):
        raise MigrationError("Privilege verification left unexpected probe objects")


def inspect_database(connection: psycopg.Connection) -> dict[str, object]:
    """Return only non-secret operational metadata."""
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        row = connection.execute(
            "SELECT current_database(), session_user, current_setting('server_version'), "
            "pg_database_size(current_database())"
        ).fetchone()
        if row is None:
            raise MigrationError("Database metadata was unavailable")
        schemas = connection.execute(
            "SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace "
            "WHERE nspname IN ('ops','raw','staging','core','marts') ORDER BY nspname"
        ).fetchall()
        roles = connection.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN "
            "('commercelens_owner','commercelens_loader',"
            "'commercelens_transformer','commercelens_reader') "
            "ORDER BY rolname"
        ).fetchall()
        defaults = connection.execute(
            "SELECT count(*) FROM pg_default_acl AS acl JOIN pg_roles AS role "
            "ON role.oid = acl.defaclrole WHERE role.rolname IN "
            "('commercelens_owner','commercelens_transformer')"
        ).fetchone()
        return {
            "capability_roles": [role[0] for role in roles],
            "default_acl_count": defaults[0] if defaults else 0,
            "database": row[0],
            "session_user": row[1],
            "server_version": row[2],
            "database_bytes": row[3],
            "sslmode": "verify-full",
            "tls_in_use": connection.pgconn.ssl_in_use,
            "schemas": dict(schemas),
        }
