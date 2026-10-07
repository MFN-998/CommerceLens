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


# Independent effective-privilege verification, usable by admin or transformer.
# Check capabilities across the entire private warehouse, including column ACLs.
def verify_reader_catalog(connection: psycopg.Connection) -> None:
    names = ["marts." + name for name in MARTS]
    row = connection.execute(
        """with warehouse as (
            select c.oid, n.nspname, c.relname, c.relkind, c.reloptions,
                r.rolname as owner, n.nspname || '.' || c.relname as qualified
            from pg_class c join pg_namespace n on n.oid=c.relnamespace
            join pg_roles r on r.oid=c.relowner
            where n.nspname in ('ops','raw','staging','core','marts')
                and c.relkind in ('r','p','v','m','f')
        ), api_roles as (
            select rolname::text as name from pg_roles
            where rolname in ('anon','authenticated','service_role')
            union all select 'public'
        ) select
            exists (select 1 from pg_roles where rolname='commercelens_reader'
                and not (rolcanlogin or rolinherit or rolsuper or rolcreatedb
                    or rolcreaterole or rolreplication or rolbypassrls))
            and not exists (select 1 from pg_auth_members
                where member=(select oid from pg_roles where rolname='commercelens_reader'))
            and has_schema_privilege('commercelens_reader','marts','USAGE')
            and not has_schema_privilege('commercelens_reader','marts','CREATE')
            and not exists (select 1 from pg_namespace
                where nspname in ('ops','raw','staging','core')
                and has_schema_privilege('commercelens_reader',oid,'USAGE,CREATE'))
            and (select count(*) from warehouse where qualified=any(%s))=3
            and not exists (select 1 from warehouse w where qualified=any(%s) and (
                relkind <> 'v' or owner <> 'commercelens_transformer'
                or exists (select 1 from pg_options_to_table(w.reloptions) o
                    where o.option_name='security_invoker' and o.option_value::boolean)
                or not has_table_privilege('commercelens_reader',oid,'SELECT')
                or has_table_privilege('commercelens_reader',oid,
                    'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN,'
                    'SELECT WITH GRANT OPTION')
                or has_any_column_privilege('commercelens_reader',oid,
                    'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')))
            and not exists (select 1 from warehouse where not qualified=any(%s) and (
                has_table_privilege('commercelens_reader',oid,
                    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
                or has_any_column_privilege('commercelens_reader',oid,
                    'SELECT,INSERT,UPDATE,REFERENCES')))
            and not exists (select 1 from api_roles r cross join pg_namespace n
                where n.nspname in ('ops','raw','staging','core','marts')
                and has_schema_privilege(r.name,n.oid,'USAGE,CREATE'))
            and not exists (select 1 from api_roles r cross join warehouse w where
                has_table_privilege(r.name,w.oid,
                    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
                or has_any_column_privilege(r.name,w.oid,'SELECT,INSERT,UPDATE,REFERENCES'))
        """,
        (names, names, names),
    ).fetchone()
    if row != (True,):
        raise ValueError("Analytics reader capability contract failed")
