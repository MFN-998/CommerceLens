-- The caller MUST wrap this entire script in a transaction and ALWAYS ROLLBACK.
-- These are ordinary schema-qualified probe objects, made disposable by rollback;
-- PostgreSQL TEMP tables cannot test the permissions/defaults of these schemas.
-- Any unexpected success raises an exception. Only insufficient_privilege is
-- accepted as an expected denial; missing-object and other errors must fail.
SET LOCAL search_path = pg_catalog;

DO $check$
DECLARE
    role_name text;
    expected_schema record;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'commercelens_owner', 'commercelens_loader',
        'commercelens_transformer', 'commercelens_reader'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = role_name
              AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
              AND NOT rolcreatedb AND NOT rolcreaterole
              AND NOT rolreplication AND NOT rolbypassrls
        ) THEN
            RAISE EXCEPTION 'Unexpected capability role attributes: %', role_name;
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_auth_members
            WHERE member = (SELECT oid FROM pg_roles WHERE rolname = role_name)
        ) THEN
            RAISE EXCEPTION 'Capability role unexpectedly inherits another role: %', role_name;
        END IF;
    END LOOP;
    FOR expected_schema IN
        SELECT * FROM (VALUES
            ('ops', 'commercelens_owner'), ('raw', 'commercelens_owner'),
            ('staging', 'commercelens_transformer'), ('core', 'commercelens_transformer'),
            ('marts', 'commercelens_transformer')
        ) AS expected(name, owner_name)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_namespace AS namespace
            JOIN pg_roles AS owner_role ON owner_role.oid = namespace.nspowner
            WHERE namespace.nspname = expected_schema.name
              AND owner_role.rolname = expected_schema.owner_name
        ) THEN
            RAISE EXCEPTION 'Missing schema or unexpected owner: %', expected_schema.name;
        END IF;
    END LOOP;
    IF NOT EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'ops' AND relation.relname = 'schema_migrations'
          AND relation.relowner = (SELECT oid FROM pg_roles WHERE rolname = 'commercelens_owner')
    ) THEN
        RAISE EXCEPTION 'Migration ledger has unexpected ownership or is missing';
    END IF;
END;
$check$;

SET LOCAL ROLE commercelens_owner;
CREATE TABLE raw.__commercelens_privilege_probe (id bigint PRIMARY KEY, value text NOT NULL);
CREATE SEQUENCE raw.__commercelens_sequence_probe;
CREATE TYPE raw.__commercelens_type_probe AS ENUM ('probe');
CREATE FUNCTION raw.__commercelens_function_probe() RETURNS integer
    LANGUAGE sql IMMUTABLE AS 'SELECT 1';
RESET ROLE;

SET LOCAL ROLE commercelens_loader;
INSERT INTO raw.__commercelens_privilege_probe VALUES (1, 'fixture');
DO $check$
BEGIN
    IF (SELECT count(*) FROM raw.__commercelens_privilege_probe) <> 1 THEN
        RAISE EXCEPTION 'Loader insert/read did not preserve the probe row';
    END IF;
    BEGIN
        UPDATE raw.__commercelens_privilege_probe SET value = 'changed' WHERE id = 1;
        RAISE EXCEPTION 'Loader unexpectedly updated raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DELETE FROM raw.__commercelens_privilege_probe WHERE id = 1;
        RAISE EXCEPTION 'Loader unexpectedly deleted raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        TRUNCATE raw.__commercelens_privilege_probe;
        RAISE EXCEPTION 'Loader unexpectedly truncated raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        CREATE TABLE raw.__commercelens_forbidden_probe (id integer);
        RAISE EXCEPTION 'Loader unexpectedly created a raw table';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM ops.schema_migrations;
        RAISE EXCEPTION 'Loader unexpectedly read the migration ledger';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM raw.__commercelens_function_probe();
        RAISE EXCEPTION 'Loader unexpectedly executed a private function';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM nextval('raw.__commercelens_sequence_probe');
        RAISE EXCEPTION 'Loader unexpectedly advanced a private sequence';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$check$;
RESET ROLE;

SET LOCAL ROLE commercelens_transformer;
CREATE TABLE staging.__commercelens_privilege_probe AS
    SELECT id, value FROM raw.__commercelens_privilege_probe;
CREATE TABLE core.__commercelens_privilege_probe AS
    SELECT id, value FROM staging.__commercelens_privilege_probe;
CREATE TABLE marts.__commercelens_privilege_probe AS
    SELECT id, value FROM core.__commercelens_privilege_probe;
CREATE TABLE marts.__commercelens_unapproved_probe (id integer);
CREATE SEQUENCE marts.__commercelens_sequence_probe;
CREATE TYPE marts.__commercelens_type_probe AS ENUM ('probe');
CREATE FUNCTION marts.__commercelens_function_probe() RETURNS integer
    LANGUAGE sql IMMUTABLE AS 'SELECT 1';
GRANT SELECT ON marts.__commercelens_privilege_probe TO commercelens_reader;
DO $check$
BEGIN
    IF (SELECT count(*) FROM marts.__commercelens_privilege_probe) <> 1 THEN
        RAISE EXCEPTION 'Transformer failed to preserve the raw probe row';
    END IF;
    BEGIN
        INSERT INTO raw.__commercelens_privilege_probe VALUES (2, 'forbidden');
        RAISE EXCEPTION 'Transformer unexpectedly inserted raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE raw.__commercelens_privilege_probe SET value = 'changed' WHERE id = 1;
        RAISE EXCEPTION 'Transformer unexpectedly updated raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        DROP TABLE raw.__commercelens_privilege_probe;
        RAISE EXCEPTION 'Transformer unexpectedly dropped raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM ops.schema_migrations;
        RAISE EXCEPTION 'Transformer unexpectedly read the migration ledger';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$check$;
RESET ROLE;

SET LOCAL ROLE commercelens_reader;
DO $check$
BEGIN
    IF (SELECT count(*) FROM marts.__commercelens_privilege_probe) <> 1 THEN
        RAISE EXCEPTION 'Reader did not see the approved mart';
    END IF;
    BEGIN
        PERFORM * FROM marts.__commercelens_unapproved_probe;
        RAISE EXCEPTION 'Reader unexpectedly read an unapproved mart';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM raw.__commercelens_privilege_probe;
        RAISE EXCEPTION 'Reader unexpectedly read raw';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM staging.__commercelens_privilege_probe;
        RAISE EXCEPTION 'Reader unexpectedly read staging';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM ops.schema_migrations;
        RAISE EXCEPTION 'Reader unexpectedly read the migration ledger';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO marts.__commercelens_privilege_probe VALUES (2, 'forbidden');
        RAISE EXCEPTION 'Reader unexpectedly wrote a mart';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        CREATE TABLE marts.__commercelens_forbidden_probe (id integer);
        RAISE EXCEPTION 'Reader unexpectedly created a mart';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM marts.__commercelens_function_probe();
        RAISE EXCEPTION 'Reader unexpectedly executed an unapproved private function';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$check$;
RESET ROLE;

DO $check$
DECLARE
    role_name text;
    schema_name text;
    relation_name text;
BEGIN
    IF has_table_privilege('commercelens_loader', 'raw.__commercelens_privilege_probe',
        'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') THEN
        RAISE EXCEPTION 'Loader has unexpected raw mutation privileges';
    END IF;
    IF has_table_privilege('commercelens_transformer', 'raw.__commercelens_privilege_probe',
        'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') THEN
        RAISE EXCEPTION 'Transformer has unexpected raw mutation privileges';
    END IF;
    IF has_table_privilege('commercelens_reader', 'marts.__commercelens_privilege_probe',
        'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') THEN
        RAISE EXCEPTION 'Reader has unexpected approved-mart mutation privileges';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        FOREACH schema_name IN ARRAY ARRAY['ops', 'raw', 'staging', 'core', 'marts'] LOOP
            IF has_schema_privilege(role_name, schema_name, 'USAGE,CREATE') THEN
                RAISE EXCEPTION 'API role % unexpectedly accesses schema %', role_name, schema_name;
            END IF;
        END LOOP;
        FOREACH relation_name IN ARRAY ARRAY[
            'ops.schema_migrations', 'raw.__commercelens_privilege_probe',
            'staging.__commercelens_privilege_probe', 'core.__commercelens_privilege_probe',
            'marts.__commercelens_privilege_probe', 'marts.__commercelens_unapproved_probe'
        ] LOOP
            IF has_table_privilege(role_name, relation_name,
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') THEN
                RAISE EXCEPTION 'API role % unexpectedly has privileges on %', role_name, relation_name;
            END IF;
        END LOOP;
        FOREACH schema_name IN ARRAY ARRAY['raw', 'marts'] LOOP
            IF has_function_privilege(role_name, schema_name || '.__commercelens_function_probe()', 'EXECUTE')
               OR has_sequence_privilege(role_name, schema_name || '.__commercelens_sequence_probe', 'USAGE,SELECT,UPDATE')
               OR has_type_privilege(role_name, schema_name || '.__commercelens_type_probe', 'USAGE') THEN
                RAISE EXCEPTION 'API role % unexpectedly has private routine/sequence/type privileges in %', role_name, schema_name;
            END IF;
        END LOOP;
    END LOOP;
END;
$check$;

-- The runner reports success only if the entire script reaches this point and
-- verifies that rollback removed the probe objects afterward.
SELECT 'warehouse privilege checks passed; transaction must be rolled back' AS result;
