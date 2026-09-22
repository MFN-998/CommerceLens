# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards, and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M2 COMPLETE; M3 PARTIALLY COMPLETE.
- Current milestone: restricted login and atomic loader implementation/tests COMPLETE.
- Current task: checkpoint validated code, then perform full source load and idempotent verification.
- Objective: all nine source tables faithfully committed, with full text/count/decimal evidence.
- SAFE TO RESUME. Full Olist upload has not started; only rolled-back synthetic fixtures ran.

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
- No dependency, source-dataset, or schema changes in this unit.

## Files

- Created: src/warehouse/loading.py, tests/test_warehouse_loading.py,
  tests/test_warehouse_loading_integration.py, tests/test_warehouse_cli.py,
  docs/warehouse-loading.md.
- Modified: src/warehouse/__main__.py, docs/warehouse-development.md,
  docs/phase-3-plan.md, WORK_STATE.md.
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
- Full-size COPY/replay, dbt and deployment: Not yet tested.

## Current Repository Condition

CLEAN / STABLE at the containing pre-load implementation checkpoint; SAFE TO RESUME.
Actual restricted login passed permission tests. All synthetic fixture rows rolled back.
Full-source production-size COPY and replay remain the first unverified acceptance step.

## Incomplete Work

- Run the full load using the restricted login, then repeat the same command for complete
  stored-snapshot verification. Record actual bytes, rows, exact money and unchanged source hashes.
- If interrupted, read docs/warehouse-loading.md: verify committed state before retry.
  Empty rows can retain allocated space; never disable capacity gates or auto-truncate.
- M4 dbt models/M5 queries and populated reconstruction remain pending. Free/views first;
  remeasure before any materialization. Audit E01–E10 retain their documented revisit gates.
- No known failing check at this checkpoint. No reset credit, paid upgrade, merge or deployment.

## Exact Next Actions

1. Inspect status/history and current usage. Confirm the pre-load checkpoint is published.
   Read docs/warehouse-loading.md; loader role/file already exist. Do not provision again.
2. Run `uv run --locked --group warehouse python -m src.warehouse load` and preserve its
   final result. Progress is not a commit; success is printed only after clean completion.
3. Run the same command again: expect verified_existing with the same load identity.
   Reconcile all counts/content/decimal evidence, actual storage and source integrity.
4. Record M3 completion and checkpoint before starting M4 according to ADR 0003/0004.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Provisioned-login checkpoint 7cbf938; credential implementation e428801.
- Source/capacity b6acd5b; applied landing schema 625dbe8; M2 foundation aa0104f/207b74f.
- Atomic-loader implementation is the containing commit. Confirm clean status and publication
  with Git; `git log -1 --format="%H %s" -- WORK_STATE.md` resolves the checkpoint.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
uv run --locked --group warehouse python -m src.warehouse inspect
uv run --locked --group warehouse python -m src.warehouse load
# Repeat load to verify the committed snapshot without adding rows.
./scripts/check.ps1 -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

Live loading-fixture suite requires an empty isolated target; do not rerun it against
populated landing. The actual-login access test remains safe after loading. See the guide.
Never print credentials, source rows, or sensitive database error details.

