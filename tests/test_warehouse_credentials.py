"""Credential handoff failures never overwrite files or leak passwords."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from dotenv import dotenv_values

from src.warehouse import credentials
from src.warehouse.config import WarehouseSettings

TEST_PASSWORD = "generated-test-password-never-used-for-a-real-connection"
TEST_VERIFIER = "SCRAM-SHA-256$synthetic-verifier-not-used-for-a-real-connection"


@pytest.fixture(params=["loader", "transformer"])
def login(request):
    purpose = request.param
    return SimpleNamespace(
        purpose=purpose,
        role=credentials.PURPOSE_USERS[purpose],
        filename=credentials.PURPOSE_FILES[purpose],
        provision=getattr(credentials, f"provision_{purpose}"),
        capability=credentials.CAPABILITY_ROLES[purpose],
    )


def settings(*, pooler: bool = False) -> WarehouseSettings:
    project = "abcdefghijklmnopqrst"
    return WarehouseSettings(
        purpose="admin",
        environment="test",
        project_ref=project,
        host="aws-0-ap-northeast-1.pooler.supabase.com" if pooler else f"db.{project}.supabase.co",
        user=f"postgres.{project}" if pooler else "postgres",
        password="dummy-administrator-password",
        sslrootcert=Path(".credentials/supabase-ca.crt"),
        _env_file=None,
    )


class FakeConnection:
    """Small fault injector; actual privilege behavior belongs to live tests."""

    def __init__(
        self,
        *,
        role_exists=False,
        sql_failure=False,
        commit_failure=False,
        encryption_failure=False,
        capability_exists=True,
        identity=("postgres", "postgres", "postgres"),
    ):
        self.role_exists = role_exists
        self.sql_failure = sql_failure
        self.commit_failure = commit_failure
        self.encryption_failure = encryption_failure
        self.capability_exists = capability_exists
        self.identity = identity
        self.attempted_create = False
        self.last_query = ""
        self.last_parameters = None
        self.queries = []
        self.pgconn = self
        self.encryption_arguments = None

    def encrypt_password(self, password, username, algorithm):
        self.encryption_arguments = (password, username, algorithm)
        if self.encryption_failure:
            raise psycopg.OperationalError(TEST_PASSWORD)
        return TEST_VERIFIER.encode("ascii")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @contextmanager
    def transaction(self):
        yield
        if self.commit_failure:
            raise psycopg.OperationalError(TEST_PASSWORD)

    def execute(self, query, parameters=None):
        self.last_query = query if isinstance(query, str) else query.as_string()
        self.last_parameters = parameters
        self.queries.append(self.last_query)
        if self.last_query.startswith("CREATE ROLE"):
            self.attempted_create = True
            if self.sql_failure:
                raise psycopg.ProgrammingError(TEST_PASSWORD)
        return self

    def fetchone(self):
        if "session_user" in self.last_query:
            return self.identity
        if "rolname = %s" in self.last_query:
            if self.last_parameters[0] in credentials.CAPABILITY_ROLES.values():
                return (1,) if self.capability_exists else None
            return (1,) if self.role_exists else None
        return None


def attach(monkeypatch, connection):
    monkeypatch.setattr(credentials, "connect", lambda _: connection)
    monkeypatch.setattr(credentials.secrets, "token_urlsafe", lambda _: TEST_PASSWORD)
    monkeypatch.setattr(credentials, "protect_credential_file", lambda _: None)


def test_existing_file_is_never_overwritten_or_connected(monkeypatch, tmp_path, login):
    path = tmp_path / login.filename
    path.write_text("existing private configuration", encoding="utf-8")

    def forbidden_connect(_):
        pytest.fail("Existing credentials must stop before a database connection")

    monkeypatch.setattr(credentials, "connect", forbidden_connect)
    with pytest.raises(credentials.ProvisioningError, match="already exists"):
        login.provision(settings(), tmp_path)
    assert path.read_text(encoding="utf-8") == "existing private configuration"


def test_existing_role_does_not_create_or_replace_credentials(monkeypatch, tmp_path, login):
    connection = FakeConnection(role_exists=True)
    attach(monkeypatch, connection)
    with pytest.raises(credentials.ProvisioningError, match="login already exists"):
        login.provision(settings(), tmp_path)
    assert not (tmp_path / login.filename).exists()
    assert not connection.attempted_create


def test_file_durability_failure_prevents_role_creation(monkeypatch, tmp_path, login):
    connection = FakeConnection()
    attach(monkeypatch, connection)

    def broken_fsync(_):
        raise OSError(TEST_PASSWORD)

    monkeypatch.setattr(credentials.os, "fsync", broken_fsync)
    with pytest.raises(credentials.ProvisioningError, match="retained") as error:
        login.provision(settings(), tmp_path)
    assert not connection.attempted_create
    assert (tmp_path / login.filename).exists()
    assert TEST_PASSWORD not in str(error.value)


def test_permission_failure_retains_empty_file_without_creating_role(monkeypatch, tmp_path, login):
    connection = FakeConnection()
    attach(monkeypatch, connection)

    def deny_permissions(path):
        assert path.read_bytes() == b""
        raise OSError(TEST_PASSWORD)

    monkeypatch.setattr(credentials, "protect_credential_file", deny_permissions)
    with pytest.raises(credentials.ProvisioningError, match="retained") as error:
        login.provision(settings(), tmp_path)
    assert (tmp_path / login.filename).read_bytes() == b""
    assert not connection.attempted_create
    assert TEST_PASSWORD not in str(error.value)


def test_permissions_are_established_before_secret_is_written(monkeypatch, tmp_path, login):
    connection = FakeConnection()
    attach(monkeypatch, connection)
    protected = []

    def protect_empty_file(path):
        assert path.read_bytes() == b""
        assert not connection.attempted_create
        protected.append(path)

    monkeypatch.setattr(credentials, "protect_credential_file", protect_empty_file)
    login.provision(settings(), tmp_path)
    assert protected == [tmp_path / login.filename]


def test_private_file_protection_preserves_existing_content(tmp_path):
    path = tmp_path / "private file with ' and [brackets].env"
    path.write_text("synthetic configuration only", encoding="utf-8")
    credentials.protect_credential_file(path)
    # The helper checks the OS permissions itself and never needs to read content.
    assert path.read_text(encoding="utf-8") == "synthetic configuration only"


def test_private_file_protection_rejects_directories(tmp_path):
    with pytest.raises(OSError, match="Could not secure"):
        credentials.protect_credential_file(tmp_path)


@pytest.mark.parametrize("failure", ["sql_failure", "commit_failure"])
def test_database_failure_retains_saved_password_and_refuses_retry(
    monkeypatch, tmp_path, failure, login
):
    connection = FakeConnection(**{failure: True})
    attach(monkeypatch, connection)
    with pytest.raises(credentials.ProvisioningError, match="Reconcile") as error:
        login.provision(settings(), tmp_path)
    path = tmp_path / login.filename
    original = path.read_bytes()
    assert dotenv_values(path)["WAREHOUSE_PASSWORD"] == TEST_PASSWORD
    assert TEST_PASSWORD not in str(error.value)
    with pytest.raises(credentials.ProvisioningError, match="already exists"):
        login.provision(settings(), tmp_path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("pooler", [False, True])
def test_success_saves_matching_target_without_returning_secret(
    monkeypatch, tmp_path, pooler, login
):
    connection = FakeConnection()
    attach(monkeypatch, connection)
    admin = settings(pooler=pooler)
    result = login.provision(admin, tmp_path)
    values = dotenv_values(tmp_path / login.filename)
    expected_user = login.role + (f".{admin.project_ref}" if pooler else "")
    assert values["WAREHOUSE_USER"] == expected_user
    assert values["WAREHOUSE_PURPOSE"] == login.purpose
    assert values["WAREHOUSE_HOST"] == admin.host
    assert values["WAREHOUSE_SSLROOTCERT"] == admin.sslrootcert.as_posix()
    assert values["WAREHOUSE_PASSWORD"] == TEST_PASSWORD
    assert result == {"role": login.role, "credential_file": login.filename}
    assert TEST_PASSWORD not in str(result)
    assert connection.encryption_arguments == (
        TEST_PASSWORD.encode("utf-8"),
        login.role.encode("ascii"),
        b"scram-sha-256",
    )
    assert TEST_PASSWORD not in "\n".join(connection.queries)
    assert TEST_VERIFIER in "\n".join(connection.queries)
    grants = [query for query in connection.queries if query.startswith("GRANT")]
    assert grants == [f'GRANT "{login.capability}" TO "{login.role}" WITH INHERIT FALSE']
    assert any(
        f'CREATE ROLE "{login.role}" LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
        "NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 2" in query
        for query in connection.queries
    )


def test_encryption_failure_never_writes_credentials_or_creates_role(monkeypatch, tmp_path, login):
    connection = FakeConnection(encryption_failure=True)
    attach(monkeypatch, connection)
    with pytest.raises(credentials.ProvisioningError, match="before saving") as error:
        login.provision(settings(), tmp_path)
    assert not (tmp_path / login.filename).exists()
    assert not connection.attempted_create
    assert TEST_PASSWORD not in str(error.value)


@pytest.mark.parametrize("restricted_purpose", ["loader", "transformer"])
def test_restricted_credentials_cannot_provision_another_role(
    monkeypatch, tmp_path, login, restricted_purpose
):
    connection = FakeConnection()
    attach(monkeypatch, connection)
    restricted = settings().model_copy(
        update={
            "purpose": restricted_purpose,
            "user": credentials.PURPOSE_USERS[restricted_purpose],
        }
    )
    with pytest.raises(credentials.ProvisioningError, match="administration settings"):
        login.provision(restricted, tmp_path)
    assert not connection.queries
    assert not (tmp_path / login.filename).exists()


def test_saved_credentials_can_load_without_admin_file(monkeypatch, tmp_path, login):
    import os

    from src.warehouse.config import load_settings

    for name in os.environ:
        if name.startswith("WAREHOUSE_"):
            monkeypatch.delenv(name)
    attach(monkeypatch, FakeConnection())
    login.provision(settings(), tmp_path)
    restricted = load_settings(tmp_path, purpose=login.purpose)
    assert restricted.user == login.role
    assert restricted.password.get_secret_value() == TEST_PASSWORD


@pytest.mark.parametrize("value", ["line\ninjection", "line\rinjection", "nul\x00", "${SECRET}"])
def test_unsupported_dotenv_values_cannot_inject_or_interpolate(value):
    with pytest.raises(credentials.ProvisioningError):
        credentials._quoted_value(value)


def test_quoted_certificate_path_survives_generated_dotenv(monkeypatch, tmp_path, login):
    attach(monkeypatch, FakeConnection())
    admin = settings().model_copy(update={"sslrootcert": Path("C:/Users/O'Brien/CA/root.crt")})
    login.provision(admin, tmp_path)
    assert dotenv_values(tmp_path / login.filename)["WAREHOUSE_SSLROOTCERT"] == (
        admin.sslrootcert.as_posix()
    )


@pytest.mark.parametrize(
    "options, message",
    [
        ({"identity": ("commercelens_ingest", "postgres", "postgres")}, "administrator identity"),
        ({"capability_exists": False}, "Apply the warehouse foundation"),
    ],
)
def test_invalid_database_identity_or_missing_foundation_saves_no_credentials(
    monkeypatch, tmp_path, login, options, message
):
    connection = FakeConnection(**options)
    attach(monkeypatch, connection)
    with pytest.raises(credentials.ProvisioningError, match=message):
        login.provision(settings(), tmp_path)
    assert not connection.attempted_create
    assert not (tmp_path / login.filename).exists()
