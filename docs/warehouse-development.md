# Development warehouse

Phase 3 M2 uses the owner's existing **CommerceLens** Supabase project as a dedicated
development target. Its dashboard branch label `main / PRODUCTION` is Supabase terminology;
this is not a CommerceLens production deployment. Do not create a duplicate project.

## Verified target and scope

- Project reference: `imvahwzlovgmaltuysmb`; AWS `ap-northeast-1` (Tokyo), Free/Nano.
- PostgreSQL 17.6; database `postgres`. Direct IPv6 was reachable from this computer.
- Direct host: `db.imvahwzlovgmaltuysmb.supabase.co`, port 5432, user `postgres`.
- Observed fallback: `aws-0-ap-northeast-1.pooler.supabase.com`, port 5432,
  user `postgres.imvahwzlovgmaltuysmb`. Copy actual settings again if the project changes.
- Dashboard allowance: 500 MB. Measure source landing, indexes, temporary build space,
  and materialized-model overhead before M3 loading. Do not upgrade a paid plan silently.
- Data API exposed schemas verified before and after bootstrap: `public`, `graphql_public`.
  Warehouse schemas are private; application/UI access is not introduced by M2.

The pinned `psycopg[binary]==3.3.6` warehouse dependency includes its PostgreSQL client
library on Windows. It avoids installing a local database server merely to connect.
It is an optional tooling group, separate from FastAPI runtime dependencies. Review the
binary/system-library deployment choice again when deploying the warehouse tooling.

## Local configuration

```powershell
uv sync --locked --group data --group warehouse
Copy-Item .env.warehouse.example .env.warehouse
```

Copy the example only on a new machine; do not overwrite an existing configuration.
Populate `.env.warehouse` privately using the actual project settings and database password.
The file and `.credentials/` are ignored by Git. Do not copy database credentials to
`web/`, `NEXT_PUBLIC_*`, documentation, screenshots, commands, or chat. Environment
variables override the dedicated file. Other application `.env` files are not read.

Download the public root certificate from **Database → Settings → SSL configuration →
Download certificate**, then store it at `.credentials/supabase-ca.crt`. The observed
official link is [Supabase's published CA](https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt).
SHA-256 verified on 2026-09-21:
`700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.
Recheck the current dashboard when refreshing this public certificate.

Connections enforce `sslmode=verify-full`: both chain and hostname verification are
required. There is no `require`/plaintext fallback. The initial Python 3.13 generic TLS
probe rejected this CA's missing key-usage extension under its strict verifier; the
actual Psycopg/libpq 18.4 client passed `verify-full` against the dashboard CA. No
certificate verification was disabled. Use the application connection check below.

The existing administrator password is used only for M2 bootstrap/checks. Capability roles
are NOLOGIN: M3/M4 must arrange narrowly scoped tool login memberships/credentials before
routine jobs. Do not run the eventual loader or dbt jobs as the administrator.

## Inspect, rehearse, migrate, verify

```powershell
uv run --locked --group warehouse python -m src.warehouse inspect
# Only before the first bootstrap, on an empty development warehouse:
uv run --locked --group warehouse python -m src.warehouse rehearse
# Apply the reviewed, committed migrations:
uv run --locked --group warehouse python -m src.warehouse migrate
uv run --locked --group warehouse python -m src.warehouse verify
```

`inspect` returns non-secret metadata. M2 accepts only explicit development/test targets,
the matched project host/admin user, database `postgres`, and port 5432. These constraints
are deliberate guards, not proof that an external project has no production users.

Migrations in `warehouse/migrations/` are sequential, checksummed, and recorded in
`ops.schema_migrations`. SQL and ledger updates share one transaction and advisory lock.
An identical replay is a no-op. Altered checksums/order, unknown history, or unexpected
existing foundation objects fail. Checksums use UTF-8 with normalized LF newlines so
Windows Git settings do not create false drift. Never edit an applied migration; add a new one.

`verify` creates named probe tables/functions/types/sequences, exercises actual allowed
operations and expected permission denials, then rolls back and checks probe cleanup.
The command does not load Olist data. API roles, including `service_role`, must have no
warehouse grants; an explicit approved-mart grant is required for the reader.

For first-bootstrap integration/recovery checks, on the same empty dedicated development
target, explicitly opt in (ordinary offline tests skip this test):

```powershell
$env:COMMERCE_WAREHOUSE_INTEGRATION = '1'
try {
    uv run --locked --group warehouse pytest tests/test_warehouse_integration.py
} finally {
    Remove-Item Env:\COMMERCE_WAREHOUSE_INTEGRATION
}
```

This checks live permission boundaries, repeated migration, checksum rejection, injected
DDL failure with ledger rollback, lock contention from another connection, complete
role/schema rollback, and reconstruction from source in a fresh session. Both complete
builds are rolled back on an empty target. After persistent bootstrap, use `verify`;
recovery tests require a new empty isolated target, not deletion of an active warehouse.

## Recovery and limits

Before first apply, the Git checkpoint and verified-empty target are the recovery boundary.
Failed migration batches roll back. After success, inspect the ledger and use forward
migrations for corrections; do not run automatic DROP/reset commands. Git checkout alone
does not undo committed database DDL. Lost empty development infrastructure can be rebuilt
from the versioned SQL after verifying the replacement target and private API configuration.

M2 reconstruction validates schema bootstrap only. It is not a populated backup/restore test.
M3–M5 still require source/content reconciliation and populated warehouse reconstruction.
Before irreplaceable/shared data, establish protected backups, retention, ownership, and a
restore test; the Free-plan dashboard's absence of backups is not a recovery guarantee.

Client verification does not establish server-wide SSL enforcement or network allowlists.
Those settings must be reviewed for the actual job/deployment environment before public use.
Database errors are reported by class/SQLSTATE without connection or row detail. Check local
configuration first; `inspect` isolates connectivity, `migrate` history, and `verify` permissions.

The [Phase 3 plan](phase-3-plan.md), [warehouse ADR](decisions/0003-warehouse-contract.md),
and [WORK_STATE](../WORK_STATE.md) record acceptance and remaining work. Connection choices
follow the [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres);
driver packaging follows the [Psycopg installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html).

## M2 completion evidence — 2026-09-21

Implementation checkpoint `aa0104f` preceded persistent migration 0001. Apply succeeded;
an identical rerun returned no pending migration. Live privilege verification passed,
including probe cleanup; five schemas and four NOLOGIN roles remain. The final measured
database size was 10,923,155 bytes (the dashboard billing metric may differ).

Offline checks: 86 passed, one opt-in database test skipped. That integration test passed
separately against the empty target before apply. Ruff, mypy (18 source files), package
compatibility (72 installed packages), frontend formatting/lint/types/build, dependency
advisory scans, and staged/history secret scans passed. The existing AnyIO deprecation
warning is carried forward. No populated-data/dbt/deployment validation is claimed.

After apply the dashboard showed 2 of 7 schemas exposed and 0 of 1 tables exposed.
M3 starts with storage sizing and least-privilege loading; the 500 MB allowance remains
an explicit acceptance gate, not an assumption that the eventual warehouse will fit.

## M3 source and landing checkpoint — 2026-09-21

[ADR 0004](decisions/0004-development-storage-budget.md) records the owner's Free/views
choice after the initial materialized budget failed. The approved conservative budget
is 466,728,242 bytes. [Load evidence](warehouse-load-plan.json) records all 1,550,922
source rows, framed content hashes, and exact decimal totals; no source rows are uploaded yet.

Migration 0002 adds immutable ops.source_loads plus nine textual raw tables. Its live
rollback test passed all nine COPY fidelity checks, permissions, integrity constraints,
server-owned attribution, repeat migration, and cleanup. Use the explicit opt-in variable
COMMERCE_WAREHOUSE_LANDING_INTEGRATION=1 with tests/test_warehouse_landing_integration.py
to rerun that reversible fixture test. The ordinary suite skips live tests.

The source registry is inserted before raw rows for immediate foreign keys. The upcoming
loader must commit only after all nine tables and complete content/money evidence match.
Restricted login provisioning, full COPY, idempotent loading, failure injection, and actual
storage reconciliation remain required before M3 is complete.

Resume verification on 2026-09-22 confirmed migration 0002 was permanently applied
from checkpoint `625dbe8`. Both ledger checksums match the repository; all nine raw
tables and the registry remain empty, API-role table access is denied, and verify-full
remains active. Measured database size: 11,234,451 bytes.

## Restricted loader credentials

Run once after migrations 0001/0002 are applied, using the private administration
configuration:

```powershell
uv run --locked --group warehouse python -m src.warehouse provision-loader
```

This creates `commercelens_ingest`, a LOGIN member only of `commercelens_loader`,
with no inherited capability, administration, role creation, replication, or RLS bypass.
Jobs explicitly select the loader capability within their transaction. The job cannot
change the schema, update/delete existing rows, impersonate an owner, or set server-owned
load attribution. Its connection limit is two. Administration credentials remain separate.

The generated password is saved in ignored `.env.warehouse.loader`, never printed.
On Windows the file receives a verified private ACL for its owner, SYSTEM, and
Administrators before any password is written; POSIX uses mode 0600. A folder's inherited
permissions alone are insufficient. Keep the administrator file equally protected.
The password is generated locally and converted to a SCRAM verifier before SQL, keeping
the clear password out of SQL statement logs. Treat both passwords and verifiers as secrets.

Credential provisioning uses the warehouse advisory lock and a transaction. It refuses
an existing role or file instead of silently rotating a password. The file is flushed to
disk before database commit. If saving, SQL, or commit acknowledgement fails, preserve
the file, inspect whether the role exists, and test the saved loader connection privately.
An empty/partial file or absent role requires explicit administrator reconciliation;
never automatically delete the evidence or rerun provisioning. A successful connection
after an uncertain commit is followed by the access test below. Future intentional rotation
must update both database and protected local configuration through a reviewed procedure.

Loader configuration requires `WAREHOUSE_PURPOSE=loader` and the loader username.
It reads only `.env.warehouse.loader`; there is no fallback to the administrator file.
Environment overrides must still match the requested purpose. Hostname, target database,
certificate verification, and development/test restrictions remain enforced.

Verify the actual login's role attributes, membership, TLS, and allowed/denied operations:

```powershell
$env:COMMERCE_WAREHOUSE_LOADER_ACCESS_INTEGRATION = '1'
try {
    uv run --locked --group warehouse pytest tests/test_warehouse_loader_access_integration.py
} finally {
    Remove-Item Env:\COMMERCE_WAREHOUSE_LOADER_ACCESS_INTEGRATION
}
```

This test uses the generated login and rolls back all probes. It works on empty or loaded
tables. It proves this connection's boundaries; it is not a deployment/network-security
audit. Use a platform secret store and reviewed credential rotation before hosted jobs.

Credential-tooling checkpoint 2026-09-22: 140 offline tests passed; three live tests
were skipped. Full formatting/lint/type/build/package/advisory/history gates passed.
Existing administrator file ACL hardened and verified; its contents were not read.
The final ACL fix preserves existing ownership; 19 credential tests passed again.
Actual loader role creation and actual-login validation remain pending.

Provisioned-login evidence 2026-09-22: committed tooling e428801 created
commercelens_ingest and its protected ignored file. The actual-login integration test
passed (17.88 seconds): TLS, non-inheriting restricted membership, role flags, expected
reads/inserts, and denied schema/owner/admin/mutation/attribution operations. No Olist
rows were uploaded. Provisioning must not be rerun against this existing login/file.

See [source loading and recovery](warehouse-loading.md) for the implemented restricted
load command, complete reconciliation, retry semantics, empty-target tests, and physical
storage recovery after interruption. Applied migrations and credentials remain unchanged.
