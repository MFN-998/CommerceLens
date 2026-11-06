"""Reject unencrypted or mismatched native fixture transport."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from native_connection import assert_verified_client_transport

SETTINGS = SimpleNamespace(
    certificate_path=lambda: Path("synthetic-ca"), host="synthetic-host", user="synthetic-user"
)
PARAMETERS = {
    "sslmode": "verify-full",
    "sslrootcert": "synthetic-ca",
    "host": "synthetic-host",
    "user": "synthetic-user",
}


def connection(tls=True, parameters=None):
    return SimpleNamespace(
        pgconn=SimpleNamespace(ssl_in_use=tls),
        info=SimpleNamespace(
            get_parameters=lambda: PARAMETERS if parameters is None else parameters
        ),
    )


def test_verified_client_transport_accepts_expected_connection():
    assert_verified_client_transport(connection(), SETTINGS)


def test_relative_certificate_configuration_uses_connects_resolved_path():
    settings = SimpleNamespace(
        sslrootcert=Path("relative-ca"),
        certificate_path=lambda: Path("resolved/synthetic-ca"),
        host=SETTINGS.host,
        user=SETTINGS.user,
    )
    parameters = {**PARAMETERS, "sslrootcert": str(Path("resolved/synthetic-ca"))}
    assert_verified_client_transport(connection(parameters=parameters), settings)
    with pytest.raises(AssertionError, match="connection verification differs"):
        assert_verified_client_transport(
            connection(parameters={**parameters, "sslrootcert": "relative-ca"}), settings
        )


@pytest.mark.parametrize("tls", [False, None, 0, 1, "true"])
def test_client_tls_is_required(tls):
    with pytest.raises(AssertionError, match="requires client TLS"):
        assert_verified_client_transport(connection(tls=tls), SETTINGS)


@pytest.mark.parametrize("key", tuple(PARAMETERS))
@pytest.mark.parametrize("missing", [False, True])
def test_mismatched_or_missing_parameters_fail_without_disclosing_values(key, missing):
    parameters = {**PARAMETERS, key: "synthetic-private-value"}
    if missing:
        parameters.pop(key)
    with pytest.raises(AssertionError) as error:
        assert_verified_client_transport(connection(parameters=parameters), SETTINGS)
    assert str(error.value) == "Native fixture connection verification differs"
