# Phase 3 M4 setup checkpoint plan

Prepared 2026-09-22 after M3 full loading and repeat verification. This is the next
bounded implementation unit, not a redesign or a claim that dbt models already exist.
Use ADR 0003 for logical schemas/grains and ADR 0004 for views-first storage constraints.

## Tooling adopted — 2026-09-22

The optional transform group and reviewed lock are now adopted in the actual repository.
Locked installation, dbt version, 151 offline tests, all existing style/type/build checks,
111-package compatibility and Python/npm advisory scans passed. Use check.ps1 -Transform
for dbt changes. Transformer credentials, project configuration and models remain pending.
The isolated experiment below is historical evidence preceding adoption.

## Validated tooling candidates

Use a separate optional `transform` dependency group in the existing Python manifest:

- `dbt-core==1.12.5`
- `dbt-postgres==1.11.0`

The candidate manifest/lock were resolved and installed in an isolated temporary
environment with the existing data/warehouse/dev/audit dependencies on Windows and
Python 3.13.14. The resolver selected 113 packages; 111 packages installed for this
platform, all passed compatibility checks and pip-audit reported no known vulnerabilities.
`dbt --version` confirmed Core 1.12.5 and Postgres adapter 1.11.0. Anonymous usage
reporting was disabled for the invocation. The experimental-parser dependency built
successfully from source. No dbt project, parse, database debug or model build has run.

The required transitive adjustments were `pathspec` 1.1.1 → 1.0.4 and `protobuf`
7.36.2 → 6.33.6. Other existing direct dependencies remain pinned. Older Core 1.11
constrains pathspec below 0.13, conflicting with the project's mypy 2.3.1 requirement
of at least 1.0; do not downgrade mypy merely to adopt that older Core line.
Review the final lock diff and rerun the existing project gates before accepting it.

This experiment did **not** change repository dependencies or its active environment.
Temporary candidates are under the local ChatGPT workspace's `m4-resolution/` and are
not authoritative project files. Reproduce from the pins above if they are unavailable.
Keep one repository manifest/lock; do not commit the temporary environment or a second lock.

Sources: [Core release](https://pypi.org/project/dbt-core/1.12.5/),
[Postgres adapter release](https://pypi.org/project/dbt-postgres/1.11.0/),
[Core dependency constraints](https://github.com/dbt-labs/dbt-core/blob/v1.12.5/core/pyproject.toml).

## Ordered implementation

1. Confirm M3 checkpoint, actual stored snapshot, Git status and current usage. Add the
   `transform` group, resolve the existing lock, review dependency changes, install locked
   groups and run the full quality/advisory gates including the transform group. Keep
   dbt tooling separate from FastAPI runtime dependencies. Checkpoint this tooling unit.
2. Extend existing purpose-specific configuration and credential provisioning for
   `transformer`, with a proposed LOGIN `commercelens_transform` that is a NOINHERIT
   member only of `commercelens_transformer`. Preserve tested private-file handling,
   failure recovery, no-overwrite rules, explicit target validation and verify-full.
   Use protected ignored `.env.warehouse.transformer`; no admin fallback for dbt jobs.
3. Add the minimal project at `dbt/dbt_project.yml`, nine raw source declarations, and
   an environment-only profile selected explicitly by a wrapper. A tracked safe profile
   may live at `dbt/profiles/profiles.yml`; all secret values come from protected settings
   via `DBT_ENV_SECRET_*` variables. Do not store credentials in YAML or generated artifacts.
4. Profile must select `role: commercelens_transformer`, verify-full and the trusted CA.
   Start with one thread and views. Map only existing `staging`, `core`, `marts` schemas;
   dbt's default custom-schema concatenation would target unintended schemas. Reject
   unapproved schema names. Disable anonymous usage reporting in project flags/wrapper.
5. Run configuration/provisioning regression tests, offline `dbt parse`, and actual-login
   `dbt debug`. Test that created views have intended ownership, transformer can read raw,
   and raw writes/admin escalation are denied. Use forced-rollback fixtures. Checkpoint
   before building staging/dimensional models and their data-quality tests.

Each unit ends with real validation, documentation, WORK_STATE update and Git checkpoint.
Views reduce storage copies but still need measured query performance. Model materialization,
business KPI definitions and frontend integration are not authorized by this setup plan.

Configuration references: [profiles](https://docs.getdbt.com/docs/local/profiles.yml),
[secret environment variables](https://docs.getdbt.com/reference/dbt-jinja-functions/env_var),
[Postgres settings](https://docs.getdbt.com/docs/local/connect-data-platform/postgres-setup),
[custom schemas](https://docs.getdbt.com/docs/build/custom-schemas).
