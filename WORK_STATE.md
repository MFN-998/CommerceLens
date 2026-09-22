# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards, and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M2 COMPLETE; M3 PARTIALLY COMPLETE.
- Completed M3 units: measured capacity decision, source contract/evidence, landing schema rehearsal and permanent application.
- Current task: finish restricted loader credentials, then atomic loading and recovery tests.
- Objective: all nine source tables loaded faithfully, atomically, and reproducibly.
- Status: SAFE TO RESUME. Full source data has **not** been uploaded.

## Completed Work

- Resumed clean published `207b74f`; live PostgreSQL 17.6, roles/schemas and verify-full match.
- Measured real temporary PostgreSQL samples with UUID/bigint lineage and primary indexes;
  all temporary tables rolled back, immutable source integrity verified before/after.
- Initial 532 MB conservative materialization budget exceeded Free's 500 MB allowance.
  Owner explicitly chose Free with views initially and a fresh review before materializing.
  Revised budget: 466,728,242 bytes. ADR 0004 records assumptions and actual-size gates.
- Source-contract module: stable content identity, logical row framing/digests, strict CSV
  text preservation, NUL/shape rejection, exact monetary validation and sums. 27 new tests pass.
- Prepared aggregate evidence for all 1,550,922 rows; exact sums match M1 observations.
- Migration 0002 was committed (625dbe8), permanently applied, and replayed with no changes.
  Resume verification on 2026-09-22 confirmed both migration checksums, nine empty tables,
  zero registry rows, and denied API-role access. Database size: 11,234,451 bytes.
- Migration 0002 creates immutable ops.source_loads and nine raw tables. Its live rollback
  test passed: COPY fidelity, expected denials, PK/FK/positive ordinal/non-null constraints,
  server-owned attribution, repeat migration, existing M2 privileges, and cleanup.

## Files

- Created: src/warehouse/source.py, tests/test_warehouse_source.py,
  warehouse/migrations/0002_source_landing.sql, tests/test_warehouse_landing_integration.py,
  docs/warehouse-storage-estimate.json, docs/warehouse-load-plan.json,
  docs/decisions/0004-development-storage-budget.md.
- Modified: tests/test_warehouse_integration.py (all-current-migration recovery expectations),
  WORK_STATE.md, docs/phase-3-plan.md, docs/warehouse-development.md.
- No new dependencies, source/staging dataset changes, or deleted/renamed repository files.
- Optional unintegrated drafts live outside Git at the local ChatGPT workspace's
  `m3-staging/src/warehouse/loading.py`, `credentials.py`, and
  `m3-staging/tests/test_warehouse_credentials.py`. They are NOT implemented/validated
  repository features. Review/adapt before use; the contracts and next actions here are authoritative.

## Technical Decisions

- All raw fields stay text, including empty strings. Row ordinals count logical CSV records.
- Stable snapshot fingerprint uses dataset/version, landing contract version, sorted file hashes;
  acquisition timestamps do not duplicate identical content. Manifest byte hash is separate.
- UUID identity plus full unique fingerprint; per-table content digests include field lengths
  and logical ordinals, so unchanged counts/money totals cannot hide changed text or row order.
- Registry inserted before raw COPY, immediate FKs; the future loader must put registry,
  all nine loads, full reconciliation, and final capacity check inside one transaction.
- Loader capability has registry SELECT and restricted INSERT; no UPDATE/DELETE, no ability
  to spoof loaded_at/by, no migration-ledger privileges. Actual job login is still pending.
- Views initially; one snapshot per capacity-reviewed target. No automatic second snapshot,
  paid upgrade, omitted data, or blanket materialization. See ADR 0004 for ceilings/reserves.

## Validation

- Storage sample measured raw estimate 293,382,593 bytes; with 25% margin 366,728,242 bytes.
  Revised total 466,728,242 bytes includes platform/model/build reserves; not a guarantee.
- Complete source preparation passed; 1,550,922 rows and all three exact money totals verified.
- Offline tests: 113 passed, 2 explicit database tests skipped. New live landing integration
  test passed separately (92 seconds); all fixture work rolled back.
- Ruff lint/format and mypy (19 source files) passed; 72 packages compatible.
- Full frontend format/lint/type/build gate passed. No dependency changes; advisory
  scan results remain historical M2 evidence. Existing AnyIO warning remains documented.
- Full production-size COPY, restricted login, retry/content corruption/failure-load tests:
  **Not yet tested / not yet implemented**. No dbt/deployment claim.

## Current Repository Condition

CLEAN / STABLE at resume; SAFE TO RESUME. Source contract b6acd5b and landing schema
625dbe8 are committed. Live 0001/0002 match checked-in SQL; no pending migration.
This handoff corrects the interrupted pre-apply record. No source records or fixture residue
remain. Publish the two existing implementation commits with this recovery checkpoint.

## Incomplete Work

- Implement reviewed restricted loader credentials/configuration and atomic COPY pipeline;
  never run routine loading as postgres. Keep generated credentials ignored and unlogged.
- Test interrupted-load rollback, idempotent retry, and corruption with unchanged counts/sums.
- Apply actual-size ceilings, load all nine sources, reconcile row/text/decimal evidence,
  verify unchanged raw hashes, and checkpoint M3 before M4 dbt models.
- M4/M5 and populated recovery remain pending. Audit E01–E10 retain their revisit gates.
- Resumed account window: 10% used (account-wide reading, not a task reservation).
  No reset credit redeemed. Earlier completed phases are not reopened.

## Exact Next Actions

1. Confirm this recovery checkpoint is published; inspect status and refresh usage.
2. Implement purpose-specific loader configuration and a restricted LOGIN member of only
   commercelens_loader. Test allowed/denied actions using that actual login.
3. Complete transactional COPY with registry/content/money/capacity checks, rollback and
   repeat-run tests; only then load all nine sources and record actual storage/evidence.

## Git State

- Branch feat/warehouse-foundation; initial published baseline 207b74f.
- Source/capacity checkpoint b6acd5b; M2 implementation aa0104f.
- Landing pre-apply checkpoint 625dbe8; no pending migration on the verified target.
- Final handoff checkpoint is the commit containing this file; verify clean status and
  origin/feat/warehouse-foundation publication. No main merge/deployment.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
git log -1 --format="%H %s" -- WORK_STATE.md
git log -1 --format="%H %s" -- warehouse/migrations/0002_source_landing.sql
uv run --locked --group warehouse python -m src.warehouse inspect
uv run --locked --group warehouse python -m src.warehouse migrate
uv run --locked --group warehouse python -m src.warehouse verify
./scripts/check.ps1
# Reversible live landing fixture test; does not load source data:
$env:COMMERCE_WAREHOUSE_LANDING_INTEGRATION = '1'
try { uv run --locked --group warehouse pytest tests/test_warehouse_landing_integration.py }
finally { Remove-Item Env:\COMMERCE_WAREHOUSE_LANDING_INTEGRATION }
```

Never print `.env.warehouse` or credentials. No production data-load command exists yet.
