"""Client transport assertions for native fixtures, including pooled connections."""

from typing import Any

from src.warehouse.config import WarehouseSettings


def assert_verified_client_transport(connection: Any, settings: WarehouseSettings) -> None:
    """Verify the actual client TLS session without exposing connection attributes."""
    if connection.pgconn.ssl_in_use is not True:
        raise AssertionError("Native fixture requires client TLS")
    parameters = connection.info.get_parameters()
    expected = {
        "sslmode": "verify-full",
        "sslrootcert": str(settings.certificate_path()),
        "host": settings.host,
        "user": settings.user,
    }
    if any(parameters.get(key) != value for key, value in expected.items()):
        raise AssertionError("Native fixture connection verification differs")
