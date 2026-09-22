# dbt development setup

Phase 3 M4 uses dbt to describe SQL transformations and their tests. Source loading remains
in the existing Python loader; dbt will read that verified raw snapshot and own only the
derived staging/core/marts objects. This setup creates no analytical models yet.

## Install and check

```powershell
uv sync --locked --group data --group warehouse --group transform
./scripts/check.ps1 -Transform -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-parse
```

The optional transform group pins dbt Core 1.12.5 and Postgres adapter 1.11.0 in the single
project lock. `-Transform` checks their version, runs the usual quality gates and performs
offline parsing. Python/npm advisory checks and secret scans require `-Security`.

`dbt-parse` uses complete synthetic settings and reads no private configuration. It checks
the tracked project, all nine raw source declarations and schema generation without a
database connection. Tests use temporary models to verify exact schemas and reject raw,
ops/public or concatenated schema names. Those probe models are never shipped.

## Restricted transformer account

Only when the transformer login and its credential file are absent, after migrations
are verified and the administration configuration is protected, run once:

```powershell
uv run --locked --group warehouse python -m src.warehouse provision-transformer
```

The login `commercelens_transform` is a NOINHERIT member only of
`commercelens_transformer`. The profile explicitly assumes that capability so derived
objects receive the correct owner/default privileges. It can read raw data and create
derived objects in the three approved schemas; it cannot write raw rows, change source
provenance/migration history, or assume loader/administrator/owner capabilities.

The generated password is saved only in protected, ignored `.env.warehouse.transformer`.
Shared provisioning retains the loader's durable-write, SCRAM, no-overwrite and uncertain
commit recovery rules described in [warehouse setup](warehouse-development.md). It never
falls back to loader or administrator credentials. If either file or role already exists,
reconcile them before proceeding; do not blindly rerun provisioning or rotate credentials.

After provisioning:

```powershell
$env:COMMERCE_WAREHOUSE_TRANSFORMER_ACCESS_INTEGRATION = '1'
try {
    uv run --locked --group warehouse pytest tests/test_warehouse_transformer_access_integration.py
} finally {
    Remove-Item Env:\COMMERCE_WAREHOUSE_TRANSFORMER_ACCESS_INTEGRATION
}
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-debug
```

The actual-login test creates tiny views inside a forced-rollback transaction, verifies
ownership, allowed raw reads and forbidden writes/escalations, checks API-role denials,
then confirms cleanup. It is safe on the populated development snapshot. `dbt-debug`
tests the actual dbt adapter connection; it does not prove model correctness or a successful build.

## Configuration and privacy decisions

- The project lives at `dbt/dbt_project.yml`; its checked-in profile is
  `dbt/profiles/profiles.yml`. That profile contains environment references, not credentials.
  The wrapper selects both paths explicitly and validates the purpose, target and CA.
- Secrets are passed through `DBT_ENV_SECRET_*` variables, which dbt scrubs from diagnostics.
  Ambient DBT/WAREHOUSE/libpq overrides are removed from the child environment. Explicit
  verify-full, trusted CA, connection timeout, one thread and capability role are enforced.
- Anonymous usage reporting and file logging are disabled. The wrapper suppresses subprocess
  output and returns a safe status or exit code; a failed debug may require private focused
  diagnosis of configuration/TLS/connectivity. Never paste raw connection exceptions or
  credentials into logs/chat. This narrow wrapper currently exposes only parse/debug.
- Generated `dbt/target`, logs and packages stay ignored. Offline tests inspect generated
  files for the synthetic password. The current wrapper uses synthetic credentials for
  manifests; don't upload artifacts from future live jobs without privacy review.
- Models default to views to honor the Free-plan storage decision. The schema macro accepts
  only staging/core/marts and avoids dbt's default schema-name concatenation. Model quality,
  tests and measured query performance remain required; views are not a substitute for them.

Next implement staging types/quality flags and dimensional models from
[ADR 0003](decisions/0003-warehouse-contract.md), then test counts, grains and relationships.
Materialization needs the capacity/performance review in
[ADR 0004](decisions/0004-development-storage-budget.md). Phase 4 business analysis and
Phase 5 KPI definitions remain outside this setup milestone.
