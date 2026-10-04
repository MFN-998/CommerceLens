-- Post-model capability grant, separate from pre-model schema migrations.
-- Run inside the dedicated transformer command's transaction; no arbitrary target.
SET LOCAL search_path = pg_catalog;

DO $check$
BEGIN
    IF session_user <> 'commercelens_transform'
       OR current_user <> 'commercelens_transform'
       OR current_database() <> 'postgres' THEN
        RAISE EXCEPTION 'Mart access requires the dedicated transformer session';
    END IF;
END;
$check$;

SET LOCAL ROLE commercelens_transformer;
DO $check$
BEGIN
    IF current_user <> 'commercelens_transformer' THEN
        RAISE EXCEPTION 'Approved transformer capability is not active';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_roles r ON r.oid=c.relowner
        WHERE n.nspname='marts' AND c.relname='mart_order_components'
          AND c.relkind='v' AND r.rolname='commercelens_transformer'
          AND NOT EXISTS (
              SELECT 1 FROM pg_options_to_table(c.reloptions) o
              WHERE o.option_name='security_invoker' AND o.option_value::boolean
          )
    ) THEN
        RAISE EXCEPTION 'Approved mart is missing or has unexpected ownership/options';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname='commercelens_reader'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
    ) OR EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE member=(SELECT oid FROM pg_roles WHERE rolname='commercelens_reader')
    ) THEN
        RAISE EXCEPTION 'Reader capability attributes or memberships differ from the contract';
    END IF;
    IF NOT has_schema_privilege('commercelens_reader','marts','USAGE')
       OR has_schema_privilege('commercelens_reader','marts','CREATE')
       OR EXISTS (
           SELECT 1 FROM pg_namespace WHERE nspname IN ('ops','raw','staging','core')
             AND has_schema_privilege('commercelens_reader',oid,'USAGE,CREATE')
       ) OR has_table_privilege('commercelens_reader','marts.mart_order_components',
           'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN,SELECT WITH GRANT OPTION')
       OR has_any_column_privilege('commercelens_reader','marts.mart_order_components',
           'INSERT,UPDATE,REFERENCES,SELECT WITH GRANT OPTION')
       OR EXISTS (
           SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname IN ('ops','raw','staging','core','marts')
             AND c.relkind IN ('r','p','v','m','f')
             AND c.oid <> 'marts.mart_order_components'::regclass
             AND (has_table_privilege('commercelens_reader',c.oid,
                 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
               OR has_any_column_privilege('commercelens_reader',c.oid,
                 'SELECT,INSERT,UPDATE,REFERENCES'))
       ) THEN
        RAISE EXCEPTION 'Reader has unexpected warehouse privileges; review before granting';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')
          AND (has_schema_privilege(rolname,'marts','USAGE,CREATE')
            OR has_table_privilege(rolname,'marts.mart_order_components',
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
            OR has_any_column_privilege(rolname,'marts.mart_order_components',
                'SELECT,INSERT,UPDATE,REFERENCES'))
    ) OR has_table_privilege('public','marts.mart_order_components',
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
      OR has_any_column_privilege('public','marts.mart_order_components',
          'SELECT,INSERT,UPDATE,REFERENCES')
      OR has_schema_privilege('public','marts','USAGE,CREATE') THEN
        RAISE EXCEPTION 'Mart API/PUBLIC exposure differs from the private contract';
    END IF;
END;
$check$;

GRANT SELECT ON TABLE marts.mart_order_components TO commercelens_reader;
RESET ROLE;
