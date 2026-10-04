"""Fixed post-model grants for approved private marts; no wildcard grants."""

from pathlib import Path

import psycopg

from src.warehouse.config import ROOT


def grant_mart_reader(connection: psycopg.Connection, root: Path = ROOT) -> dict[str, str]:
    """Apply the reviewed grant atomically; reapplication keeps the same permissions.

    Model construction must precede this operation during reconstruction. Source SQL
    guards the actual role/target and privilege drift; incompatible state fails closed.
    Success must be reported only after transaction and connection exit cleanly.
    """
    script = (root / "warehouse/access/mart_order_components.sql").read_text("utf-8")
    with connection.transaction():
        connection.execute(script, prepare=False)
    return {"status": "granted", "model": "marts.mart_order_components", "capability": "SELECT"}
