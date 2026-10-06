"""Fixed additional Phase5 mart grants, preserving the private NOLOGIN reader."""

from pathlib import Path

import psycopg

from src.warehouse.config import ROOT

MARTS = ("mart_order_components", "mart_order_kpis", "mart_item_kpis")


def grant_analytics_reader(connection: psycopg.Connection, root: Path = ROOT) -> None:
    """Review every approved mart before committing exact SELECT grants atomically."""
    # Reuse the audited guard for session, capability attributes, ownership,
    # API/PUBLIC/schema/column denials and write/grant-option denials. Only the
    # fixed SELECT relation allowlist expands; all three are checked in one transaction.
    base = (root / "warehouse/access/mart_order_components.sql").read_text("utf-8")
    exclusion = "c.oid <> 'marts.mart_order_components'::regclass"
    replacement = "c.oid not in (" + ",".join(f"'marts.{name}'::regclass" for name in MARTS) + ")"
    if base.count(exclusion) != 1:
        raise ValueError("Approved mart grant guard changed; review required")
    with connection.transaction():
        for name in MARTS:
            # Replace the target first, then expand only the exact exclusion guard.
            script = base.replace("mart_order_components", name)
            script = script.replace(exclusion.replace("mart_order_components", name), replacement)
            connection.execute(script, prepare=False)
