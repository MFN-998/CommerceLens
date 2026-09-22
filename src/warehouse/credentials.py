"""Provision one development loader login without printing or replacing credentials."""

import os
import secrets
import stat
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql

from src.warehouse.config import ROOT, WarehouseSettings, connect
from src.warehouse.migrations import LOCK_ID

LOADER_ROLE = "commercelens_ingest"
LOADER_ENV = ".env.warehouse.loader"

# Fixed code: the path is data from the subprocess environment, never interpolated
# into PowerShell. No file content is read, and all subprocess output is discarded.
_PROTECT_WINDOWS_FILE = r"""
$ErrorActionPreference = 'Stop'
try {
    $path = $env:COMMERCELENS_PRIVATE_FILE
    if (-not [System.IO.File]::Exists($path) -or
        ([System.IO.File]::GetAttributes($path) -band
            [System.IO.FileAttributes]::ReparsePoint)) { exit 1 }
    $owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $allowed = @($owner.Value, 'S-1-5-18', 'S-1-5-32-544') | Select-Object -Unique
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    # Preserve ownership; changing the DACL must not require ownership privileges.
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($value in $allowed) {
        $sid = [System.Security.Principal.SecurityIdentifier]::new($value)
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    [System.IO.File]::SetAccessControl($path, $acl)
    $actual = [System.IO.File]::GetAccessControl($path)
    $actualOwner = $actual.GetOwner([System.Security.Principal.SecurityIdentifier])
    $rules = $actual.GetAccessRules($true, $true,
        [System.Security.Principal.SecurityIdentifier])
    if (-not $actual.AreAccessRulesProtected -or $actualOwner.Value -ne $owner.Value -or
        $rules.Count -ne $allowed.Count) { exit 1 }
    foreach ($rule in $rules) {
        $fullControl = [System.Security.AccessControl.FileSystemRights]::FullControl
        if ($rule.IsInherited -or $rule.IdentityReference.Value -notin $allowed -or
            $rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
            $rule.FileSystemRights -ne $fullControl) {
            exit 1
        }
    }
} catch { exit 1 }
exit 0
"""


class ProvisioningError(ValueError):
    """Safe provisioning/recovery instructions without connection or SQL details."""


def protect_credential_file(path: Path) -> None:
    """Restrict one existing regular file; never inspect or output its contents.

    Windows retains access only for the current owner, SYSTEM, and Administrators.
    POSIX uses owner read/write. Failure is closed: callers must not write a secret.
    The helper also supports hardening an existing administration credential file.
    """
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError("A regular credential file is required")
        if os.name == "nt":
            system_root = os.environ.get("SystemRoot")
            if not system_root:
                raise OSError("Windows system directory is unavailable")
            executable = (
                Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            )
            result = subprocess.run(
                [
                    str(executable),
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _PROTECT_WINDOWS_FILE,
                ],
                env={**os.environ, "COMMERCELENS_PRIVATE_FILE": str(path.absolute())},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                raise OSError("Windows credential permissions could not be verified")
        else:
            path.chmod(0o600)
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise OSError("Credential permissions could not be verified")
    except (OSError, subprocess.SubprocessError):
        raise OSError(
            "Could not secure the credential file; do not store credentials in it"
        ) from None


def _quoted_value(value: str) -> str:
    """Preserve dotenv values without line injection or variable interpolation."""
    if any(character in value for character in ("\r", "\n", "\x00", "${")):
        raise ProvisioningError("Loader configuration contains an unsupported file value")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _credential_content(settings: WarehouseSettings, password: str) -> str:
    username = LOADER_ROLE
    if settings.user == f"postgres.{settings.project_ref}":
        username += f".{settings.project_ref}"
    values = {
        "WAREHOUSE_PURPOSE": "loader",
        "WAREHOUSE_ENVIRONMENT": settings.environment,
        "WAREHOUSE_PROJECT_REF": settings.project_ref,
        "WAREHOUSE_HOST": settings.host,
        "WAREHOUSE_PORT": str(settings.port),
        "WAREHOUSE_DATABASE": settings.database,
        "WAREHOUSE_USER": username,
        "WAREHOUSE_PASSWORD": password,
        "WAREHOUSE_SSLROOTCERT": settings.sslrootcert.as_posix(),
    }
    return (
        "# Private loader credentials. Never commit, print, or share this file.\n"
        + "\n".join(f"{name}={_quoted_value(value)}" for name, value in values.items())
        + "\n"
    )


def provision_loader(admin_settings: WarehouseSettings, root: Path = ROOT) -> dict[str, str]:
    """Create an isolated loader login and durably save its password before SQL commits.

    Repeated calls never rotate passwords or overwrite a local file. A failure after
    file creation retains that file because a failed commit acknowledgement can leave
    the database outcome uncertain. An administrator must reconcile both sides before
    recovery; this function deliberately does not auto-delete or auto-retry either.
    """
    if admin_settings.purpose != "admin":
        raise ProvisioningError("Loader provisioning requires administration settings")
    path = root / LOADER_ENV
    if path.exists() or path.is_symlink():
        raise ProvisioningError("Loader credential file already exists; reconcile before retrying")

    file_created = False
    try:
        with connect(admin_settings) as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
            identity = connection.execute(
                "SELECT session_user, current_user, current_database()"
            ).fetchone()
            if identity != ("postgres", "postgres", "postgres"):
                raise ProvisioningError("Loader provisioning requires the administrator identity")
            exists = connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (LOADER_ROLE,)
            ).fetchone()
            if exists is not None:
                raise ProvisioningError("Loader login already exists; reconcile before retrying")
            capability = connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = 'commercelens_loader'"
            ).fetchone()
            if capability is None:
                raise ProvisioningError("Apply the warehouse foundation before provisioning")

            password = secrets.token_urlsafe(32)
            # Compute the SCRAM verifier in libpq so SQL statement logs never receive
            # the clear password. The verifier remains sensitive and is never logged.
            verifier = connection.pgconn.encrypt_password(
                password.encode("utf-8"), LOADER_ROLE.encode("ascii"), b"scram-sha-256"
            ).decode("ascii")
            content = _credential_content(admin_settings, password)
            # O_EXCL also rejects a concurrent file creator or a dangling symlink.
            # Secure the empty file before writing any credential content.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            file_created = True
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                protect_credential_file(path)
                if path.is_symlink() or not os.path.samestat(
                    path.stat(), os.fstat(handle.fileno())
                ):
                    raise OSError("Credential file identity changed before writing")
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD {}"
                ).format(sql.Identifier(LOADER_ROLE), sql.Literal(verifier))
            )
            # PostgreSQL 17 defaults ADMIN to false and SET to true for a new
            # membership. NOINHERIT is also explicit on this capability grant.
            connection.execute(
                sql.SQL("GRANT commercelens_loader TO {} WITH INHERIT FALSE").format(
                    sql.Identifier(LOADER_ROLE)
                )
            )
            connection.execute(
                sql.SQL("ALTER ROLE {} SET search_path = pg_catalog").format(
                    sql.Identifier(LOADER_ROLE)
                )
            )
    except FileExistsError:
        raise ProvisioningError(
            "Loader credential file already exists; reconcile before retrying"
        ) from None
    except (psycopg.Error, OSError):
        if file_created:
            raise ProvisioningError(
                "Loader provisioning did not complete reliably; local credential file retained. "
                "Reconcile the database role and local file before retrying"
            ) from None
        raise ProvisioningError(
            "Loader provisioning failed before saving credentials; no error detail logged"
        ) from None
    return {"role": LOADER_ROLE, "credential_file": path.name}
