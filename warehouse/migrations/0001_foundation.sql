-- Run only through the migration runner, inside its transaction and advisory lock.
-- Plain CREATE intentionally rejects an unexpected existing warehouse foundation.
-- This migration has no credentials, source tables, or M3 load-registry objects.
SET LOCAL search_path = pg_catalog;

DO $check$
BEGIN
    IF session_user <> 'postgres' OR current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Foundation bootstrap requires the existing postgres administrator';
    END IF;
END;
$check$;

CREATE ROLE commercelens_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE commercelens_loader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE commercelens_transformer
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE commercelens_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- The existing project administrator can assume these capabilities for migrations
-- and verification. No application or API role receives this membership.
GRANT commercelens_owner, commercelens_loader,
    commercelens_transformer, commercelens_reader TO postgres;

CREATE SCHEMA ops AUTHORIZATION commercelens_owner;
CREATE SCHEMA raw AUTHORIZATION commercelens_owner;
CREATE SCHEMA staging AUTHORIZATION commercelens_transformer;
CREATE SCHEMA core AUTHORIZATION commercelens_transformer;
CREATE SCHEMA marts AUTHORIZATION commercelens_transformer;

REVOKE ALL ON SCHEMA ops, raw, staging, core, marts
    FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA raw TO commercelens_loader, commercelens_transformer;
GRANT USAGE ON SCHEMA marts TO commercelens_reader;

-- Defaults apply to the actual creator, not to its inherited memberships.
-- Global revokes are deliberate: a per-schema revoke cannot undo global defaults,
-- including PostgreSQL's PUBLIC function EXECUTE and type USAGE defaults.
SET LOCAL ROLE commercelens_owner;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON SEQUENCES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON FUNCTIONS
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON TYPES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON SCHEMAS
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT SELECT, INSERT ON TABLES
    TO commercelens_loader;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT SELECT ON TABLES
    TO commercelens_transformer;

CREATE TABLE ops.schema_migrations (
    version text PRIMARY KEY,
    checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
    applied_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by text NOT NULL
);

RESET ROLE;
SET LOCAL ROLE commercelens_transformer;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON SEQUENCES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON FUNCTIONS
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON TYPES
    FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON SCHEMAS
    FROM PUBLIC, anon, authenticated, service_role;
-- Reader access is an explicit grant on each approved mart, not a default grant
-- covering every future intermediate, diagnostic, or sensitive model.
RESET ROLE;
