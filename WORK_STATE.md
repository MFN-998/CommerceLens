# CommerceLens work state

Updated: 2026-09-25. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M3 COMPLETE; M4 IN PROGRESS.
- Current milestone: dbt tooling/bootstrap and live transformer setup COMPLETE.
- Current task: checkpoint verified live setup; next is one customer staging model.
- Objective: tested analytical warehouse; M4 models/tests and M5 remain pending.
- SAFE TO RESUME. Weekly budget constrains scope: 10% at session start, last observed
  8% weekly / 82% five-hour remaining. No model implementation started this session.

## Completed Work

- Resumed clean published e160563; reconciled stale pending-checkpoint wording with Git.
- Preflight confirmed intended development project, verify-full TLS, applied migration
  checksums, original M3 source registry and absence of transformer role/credential file.
- Provisioned commercelens_transform once using reviewed implementation 6183918.
- Both actual transformer and existing loader access tests passed; dbt-debug passed.
- Checked private-file ACL/ignore rules, artifact secret absence, database capacity,
  unchanged migration/registry metadata and rollback cleanup. Updated phase/setup evidence.
- Historical M3: all nine source tables / 1,550,922 rows loaded and full idempotent replay
  verified. docs/warehouse-load-verification.json remains its acceptance evidence.

## Files

- Modified: WORK_STATE.md, docs/dbt-development.md, docs/dbt-setup-plan.md,
  docs/phase-3-plan.md, docs/decisions/0003-warehouse-contract.md.
- Created locally only: protected ignored .env.warehouse.transformer.
- No source-code/dependency/migration changes, deletions or renames this session.
- Existing admin/loader credentials, raw data and dbt configuration preserved.

## Technical Decisions

- Dedicated NOINHERIT LOGIN, member only of commercelens_transformer; explicit role,
  trusted CA and verify-full. No administrator fallback or credential overwrite.
- One thread, views and only staging/core/marts schemas. Raw remains read-only to dbt.
- Optional pinned dbt Core 1.12.5 / Postgres adapter 1.11.0; one manifest/lock.
- Safe wrapper currently supports only parse/debug; build/test requires a reviewed extension.
- Free-plan raw/database ceilings remain 367M/400M bytes. Review capacity/performance
  before materialization. No paid upgrade, source omission or business KPI definitions.
- Live permission tests use unconditional rollback. Git rollback does not remove database
  roles: retain the valid private credentials; never rerun provision-transformer blindly.

## Validation

- 2026-09-25: 2 actual-login integration tests passed in 26.05s (transformer and loader).
  Verified TLS/identity, membership/NOINHERIT/connection limit, explicit role, raw read,
  denied raw writes/escalation/ledger access, view ownership, API denials and cleanup.
- Actual dbt-debug passed with restricted credentials and verify-full profile.
- Windows ACL verified: current owner/SYSTEM/Administrators only, no inherited entries.
  Initial sandbox ACL inspection was denied; elevated metadata-only verification passed.
- Read-only postflight: migration hashes match, original load registry unchanged, zero
  derived relations, database 287,050,899 bytes; no password in 5 generated dbt files.
- Historical 2026-09-22 full gate: 203 passed / 14 opt-in skipped, Ruff, mypy 22 files,
  offline parse, frontend format/lint/types/build, 111 compatible packages, advisory and
  secret scans passed. Existing documented AnyIO warning. Not rerun for documentation-only
  changes; current live tests supply the previously missing connection/access evidence.
- Full raw content was not rescanned/reloaded this session. M3 content evidence remains
  historical (raw/database bytes then 275,750,912 / 287,026,323).
- No analytical dbt build/data tests, E2E or deployment validation yet.

## Current Repository Condition

CLEAN / STABLE implementation and verified live setup; only the listed documentation is
pending the containing checkpoint at writing. SAFE TO RESUME. No known failing checks.
M3 remains populated; do not rerun empty-target fixtures against this database.

## Incomplete Work

- M4 staging/core models, dbt data tests/build and M5 technical marts/queries/reconstruction.
- Extend wrapper for narrowly selected model build/test before executing models; retain
  private settings, safe diagnostics, approved schemas, one thread and views.
- Audit E01–E10 revisit gates remain; E05/E06 have documented partial Phase 3 remediation.
- No usage credit redeemed, paid upgrade, merge, deployment or production readiness claim.

## Exact Next Actions

1. Inspect usage/status/history and read ADR 0003 plus dbt development acceptance. Inspect
   src/warehouse/dbt_runner.py and tests/test_warehouse_dbt.py to plan the selected build/test
   extension. Both restricted accounts already exist: do not provision them again.
2. Implement one atomic customer staging unit: dbt/models/staging/stg_customers.sql and
   model/test YAML. Preserve one row per customer_id, lineage, identifiers/ZIP text and
   city/state meaning; repeated customer_unique_id is valid. Document empty-string/null
   handling; no arbitrary address, deduplication, geography expansion or KPI policy.
3. Validate offline fixtures (leading-zero ZIP, repeated identity, missing text/invalid
   keys), parse and selected live dbt build/tests. Reconcile raw/staging counts, lineage and
   fields; verify view ownership/API denials. Failed model tests are not accepted builds.
4. Run applicable full gates and secret scans, document any persistent view and restoration
   path, update this state and checkpoint before implementing additional staging/core models.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Resumed published e160563; implementation 6183918; tooling dfecdbc; M3 2604e82.
- Working tree was clean before this session. Only listed documentation is changed.
- Current acceptance/handoff is the containing commit; resolve it with
  git log -1 --format="%H %s" -- WORK_STATE.md.
- Review diff, scan staged export and post-commit history, publish then confirm clean status.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
uv sync --locked --group data --group warehouse --group transform
./scripts/check.ps1 -Transform -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-parse
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-debug
```

Actual-login opt-in test commands are in docs/dbt-development.md. Do not print private
configuration, raw records or driver errors. Development target remains Supabase CommerceLens.
