# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards, and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M3 COMPLETE. Phase 3 overall remains IN PROGRESS.
- Current milestone: full source loading, content reconciliation and repeat verification COMPLETE.
- Current task: prepare the next bounded M4 dbt tooling/configuration unit.
- Objective: a tested analytical warehouse; M4 models and M5 marts/recovery are still required.
- M3 COMPLETE / SAFE TO RESUME at M4. All 1,550,922 source rows are committed privately.

## Completed Work

- Reconciled interrupted session: migration 0002 was applied, with identical replay a no-op.
  Both ledger checksums match Git; nine raw tables and registry were empty on resume.
  API roles have no table access. Published missing implementation/handoff checkpoints.
- Source contracts preserve all 1,550,922 rows, exact decimal totals, framed text hashes,
  empty values, logical row ordinals, and immutable provenance. Migration 0002 adds
  ops.source_loads and nine raw text tables. Prior real migration/COPY fixture test passed.
- Current credential unit adds isolated admin/loader configuration, exclusive durable
  private-file creation, client-side SCRAM verifier generation, refusal to overwrite an
  existing role/file, and explicit recovery when commit acknowledgement is uncertain.
- Existing administrator configuration ACL protected and verified without reading contents.
  Fixed Windows module loading with direct .NET ACL APIs and preserved existing ownership
  so protecting an existing file does not request unnecessary ownership privileges.
- Provisioned commercelens_ingest using committed e428801; saved protected ignored
  .env.warehouse.loader. Actual login boundary test passed (17.88 seconds), including TLS,
  role attributes, exact membership, SELECT/INSERT access and denied schema/admin/mutation actions.
- Atomic client COPY implementation now reconciles full row text/order/counts and exact
  decimal sums; verifies source before/after; enforces one snapshot and actual storage gates.
- Review fixed the administrator-refusal test to roll back even on a guard regression;
  documented physical-space maintenance after failed COPY and added capacity refusal coverage.
- Full load committed using restricted login; repeat fully verified the same snapshot,
  preserving original attribution and adding no rows. Aggregate receipt persisted in docs.
- M4 candidates resolved/installed in an isolated environment only: dbt-core 1.12.5,
  dbt-postgres 1.11.0, 111 installed packages compatible and no known advisories.
  Repository dependency adoption, dbt parse/debug/models have NOT been done.
- No dependency, source-dataset, or schema changes in the actual repository this unit.

## Files

- Created: src/warehouse/loading.py, tests/test_warehouse_loading.py,
  tests/test_warehouse_loading_integration.py, tests/test_warehouse_cli.py,
  docs/warehouse-loading.md, docs/warehouse-load-verification.json, docs/dbt-setup-plan.md.
- Modified: src/warehouse/__main__.py, docs/warehouse-development.md,
  docs/phase-3-plan.md, docs/engineering-audit-phase-1-2.md, README.md, WORK_STATE.md.
- Existing source.py, source evidence, migrations 0001/0002 and original datasets unchanged.
- No dependencies, deleted/renamed files, schema changes or later-phase implementation.
- .env.warehouse.loader is protected, ignored and provisioned; never print or recreate it.
- Outside-repository m3-staging drafts are now superseded by the actual repository files.

## Technical Decisions

- Dedicated LOGIN commercelens_ingest must be a non-inheriting member only of
  commercelens_loader. No administrator fallback. Loader purpose reads only its
  dedicated ignored configuration file; target and verify-full checks remain mandatory.
- Before writing secrets, private files require owner-only POSIX permissions or Windows
  owner/SYSTEM/Administrators ACL. Existing inherited Windows folder permissions proved
  too broad; protect administrator credentials as well.
- Persist the local credential before committing the database role. Uncertain failures
  retain the file for reconciliation; never silently overwrite, rotate, or delete it.
- All nine COPY operations, registry insertion, full text/count/decimal reconciliation,
  and final capacity check must share one transaction and warehouse advisory lock.
- Free/views decision is unchanged: one snapshot per reviewed target; raw ceiling
  367,000,000 bytes, database ceiling 400,000,000 bytes. Initial models use views.
  ADR 0004 preserves the failed initial 532 MB materialization scenario and approved
  revised 466,728,242-byte budget. Estimates are not guarantees or WAL/disk guarantees.

## Validation

- Resume 2026-09-22: actual PostgreSQL 17.6, verify-full/TLS, schemas/roles unchanged;
  migrations 0001/0002 match, registry/raw empty, API table denials pass.
  Database: 11,234,451 bytes before credential work.
- Full credential checkpoint gate: 140 tests passed, three explicit live tests skipped;
  Ruff lint/format (54 files), mypy (20 source files), package compatibility, frontend
  formatting/lint/types/build, Python/npm advisory and Git-history secret scans passed.
  One existing AnyIO deprecation warning remains. Windows ACL failures were corrected;
  all 19 credential tests passed again after the ownership-preserving fix.
  Actual role provisioning succeeded; actual-login permission test passed separately.
- Historical source/landing checkpoint: 113 offline tests passed, two live tests skipped;
  real landing rollback test passed separately. Ruff/mypy/packages/frontend gates passed.
- Recovery documentation staged/history secret scans passed; bcd85a9 published.
- Atomic loader: 151 offline tests passed, 13 explicit live cases skipped by default;
  all 10 actual-loader recovery tests passed separately in 320.24 seconds with cleanup.
  Full Ruff lint/format (59 files), mypy (21 source files), frontend checks/build,
  package compatibility, Python/npm advisory and history secret scans passed.
  The existing AnyIO warning remains; no checks disabled.
- Full-size COPY and complete replay passed: 1,550,922 rows, same load UUID
  12051b6f-5396-591b-bc5a-f86148eabb6f. Original manifest and all nine file hashes unchanged.
  Full logical text digests/counts and exact money independently reconciled.
  Raw size 275,750,912 bytes; database 287,026,323 bytes at final acceptance.
  API schema access denied for anon/authenticated/service_role. See aggregate receipt.
- M4 isolated tooling: lock resolution, installed-package compatibility, dbt --version and
  advisory scan passed. No dbt project parse/build, transformer login or deployment tested.

## Current Repository Condition

CLEAN / STABLE at the containing M3 completion checkpoint. All source rows are committed;
the repeat command verified_existing with unchanged identity and original provenance.
Source files, migrations, role isolation and existing application remain intact.
Do not rerun empty-landing fixture tests on this populated target or provision the loader again.

## Incomplete Work

- M4: adopt the tested dbt version candidates in an optional group; validate the actual
  project environment; implement restricted transformer settings/login and minimal dbt
  project/profile/source configuration before model implementation. See docs/dbt-setup-plan.md.
- Then build/test staging and dimensional models with explicit quality flags and retained rows.
- M5: safe order-grain technical mart, example queries/plans, access and populated reconstruction.
- Views first. Remeasure storage, rebuild overlap and performance before materialization.
- E01–E10 audit revisit gates remain; E05/E06 now have partial Phase 3 implementation evidence.
- No known failing check. No merge, deployment, paid upgrade, reset credit or production-readiness claim.
- Usage reached 71% during acceptance; completed M3 and documented isolated M4 compatibility
  proof rather than beginning credential/dependency changes across the actual project.

## Exact Next Actions

1. Read docs/dbt-setup-plan.md and ADR 0003/0004; inspect Git status/history and current usage.
   Confirm M3 completion evidence in docs/warehouse-load-verification.json against actual state.
2. Implement M4 tooling: add optional transform group with dbt-core==1.12.5 and
   dbt-postgres==1.11.0 to pyproject.toml; resolve/review the single uv.lock, install locked
   groups, include transform in quality/advisory checks, verify dbt version, and checkpoint.
3. Implement/test transformer purpose and protected provisioning, then minimal dbt project,
   secret-safe profile/wrapper and source declarations; run parse/debug and role-boundary tests.
4. Checkpoint configuration before building staging/core models. Preserve grains and warnings;
   do not start Phase 4 business analysis or Phase 5 KPI definitions.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Published pre-load code checkpoint 35ba3c5; loader provisioning evidence 7cbf938;
  credential tooling e428801; applied landing migration 625dbe8.
- M3 completion evidence is the containing commit. Confirm clean status and publication.
- Resolve handoff commit with `git log -1 --format="%H %s" -- WORK_STATE.md`.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
uv run --locked --group warehouse python -m src.warehouse inspect
# Full committed-snapshot verification; adds no rows for the same verified source:
uv run --locked --group warehouse python -m src.warehouse load
./scripts/check.ps1 -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

The load command streams all stored content on verification. Use it when needed, not
after every documentation edit. Empty-target loading/bootstrap tests need a replacement
isolated target; the actual-login access test remains safe on this populated database.
Never print credentials, raw records or sensitive database diagnostics.
