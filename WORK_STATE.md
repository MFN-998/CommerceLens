# CommerceLens work state

Authoritative handoff; verify actual Git/files on resume. No secrets or source records.
Updated 2026-10-01.

## Project State

- Current phase: Phase 3, Database/SQL/Analytics Engineering.
- Current milestone/task: M4 orders staging COMPLETE; next atomic source is order_items.
- Objective: tested analytical warehouse per master plan/ADR 0003, preserving Phase 2 source
  meaning and the Free/views-first decision. Phase 4 and the required exit audit have not begun.

## Completed Work

- Phases 1–2 and their professional-practices remediation are complete; do not redo them.
- M1 contracts, M2 isolated foundation and M3 all-nine-table landing complete.
  Raw retains 1,550,922 rows; no source reload or migration rerun required.
- Customer/seller/category translation staging previously accepted: 99,441/3,095/71 rows
  and 12/11/8 dbt tests. Resume read-only acceptance checks passed for those three models.
- Products complete/published 7a2e1e6: 32,951 rows, first/repeat 16 dbt tests, 31 native
  synthetic cases, actual-login physical/access acceptance and repeat identity/grants preserved.
- Orders source-preserving projection, strict guarded timestamps, 12 missing/reversal flags,
  25 dbt tests, offline/native and physical acceptance complete. All 99,441 source rows retained.
- Six previously approved obsolete local scan copies were removed earlier; no other approval.

## Files

- Created dbt/macros/source_timestamp.sql, dbt/models/staging/stg_orders.sql/.yml;
  dbt/tests/stg_orders_lineage_unique/source_domains/source_reconciliation.sql.
- Created tests/test_warehouse_order_staging.py, test_warehouse_order_integration.py,
  test_warehouse_order_postgres_integration.py, docs/order-staging.md and aggregate verification JSON.
- Modified src/warehouse/dbt_runner.py (only selected stg_orders addition), WORK_STATE.md,
  docs/phase-3-plan.md and docs/customer-staging.md (current selected models/links).
- Products files/guide/evidence already committed. No files deleted/renamed this session.
- Ignored UUID test/dbt artifacts retained. Scratch candidates are not repository inputs.

## Technical Decisions

- Orders retain all eight source fields, lineage, literal IDs/status and every row. Customer
  reference targets stg_customers; child aggregation belongs to later core/mart units.
- Five naive timestamps, no invented timezone: canonical ASCII YYYY-MM-DD HH:MM:SS,
  real calendars, h00-23/m00-59/s00-59 and whole-second Phase 2 bounds
  1677-09-21 00:12:44 through 2262-04-11 23:47:16. Guard text before CAST.
- Invalid nonempty input becomes typed NULL and fails blocking domains; raw missing flags
  remain false. Delivered-missing diagnostics use typed absence; reversals retain events.
- No event repair, estimate sequencing rule, duration, KPI eligibility or analysis.
- Restrictive transformer/verify-full TLS and selected runner; no raw writes/credential change.
  Compatible CREATE OR REPLACE retains views and commits before tests. Failed acceptance
  is not automatic rollback. No deletion or full refresh.
- Recommended deferred parser compatibility debt: installed Phase 2 pandas accepts
  nonpadded dates, leap-second rollover and dynamic now/today. Strict warehouse rejection
  mitigates this for the verified snapshot. Owner: project maintainer. Revisit/fix before
  accepting a different source version; do not reopen completed phases or run the full audit.

## Validation

- Orders repository Ruff lint/format passed (83 Python files); mypy passed (22 implementation files).
- Offline dbt parse passed; retained artifact .artifacts/dbt/70d5b38e2d6e4dbd98f38f93e8a096c3.
- Warehouse/API regression: 329 passed, 137 deliberately skipped opt-in live tests;
  known AnyIO deprecation warning only. First command had an interpreter-path typo and
  did not run tests; corrected command produced these actual results.
- Native read-only order synthetic cases: 87 passed, actual projection/domain/generic tests,
  strict calendar/bounds/format, source missingness, all reversals, customer references and
  inline-constant cast planning. Per-case savepoints prevent cascaded transaction failures.
- Orders first/repeat builds each passed one view and 25 tests; 99,441 raw/staging rows.
  Actual-login physical/access acceptance passed. Repeat OID/owner/grants unchanged.
  All 12 flag counts match independent raw counts; missing approval/carrier/customer
  160/1783/2965; delivered-missing 14/2/8; reversals 0/166/0/1359/61/23.
  Password absent from first/repeat artifacts; database bytes 287116435 <400M.
  Aggregate evidence: docs/order-staging-verification.json.
- Products first/repeat 16 tests, physical/access and 31 native cases accepted earlier today.
- Complete orders implementation staged contents/history secret scans passed before publication.
  Initial scanner false positive was checklist prose; rephrased it, no rules disabled.
  Final acceptance publication requires the same staged/history scans. Dependencies unchanged;
  full source/frontend/advisory gate last historical
  pass 2026-09-22, not rerun here because cleanup needs approval/adaptation.
- No deployment/E2E/full post-Phase-3 governance audit this session.

## Current Repository Condition

STABLE / SAFE TO RESUME. Products and orders atomic units COMPLETE. Five of nine staging
sources accepted; Phase 3 remains incomplete. No known current failed checks or partial
model implementation. Verify actual Git cleanliness/publication on resume.

## Incomplete Work

- Four staging sources: order_items, order_payments, order_reviews, geolocation.
- Core dimensions/facts/tests and M5 technical marts/SQL/performance/reconstruction pending.
- Audit E01–E10 retain revisit gates; focused parser debt described above. Full check.ps1
  cleanup needs approval/adaptation. After all Phase 3 verified, perform required full
  governance audit/corrections/regression before Phase 4.

## Exact Next Actions

1. Check usage, Git status/recent history; read docs/order-staging.md and its evidence.
   Confirm containing acceptance checkpoint published/clean; do not repeat earlier units.
2. Read TABLES["order_items"] in src/validation/contracts.py, source money ingestion in
   src/warehouse/loading.py and ADR 0003. Prepare stg_order_items at (order_id, order_item_id),
   preserving all keys/lineage, exact price/freight (no Float64 or rounding) and shipping date.
   References target the now-accepted order/product/seller views; preserve source anomalies.
3. Add meaningful numeric/date/grain/reference/reconciliation tests; retained/native validation,
   code checkpoint, then selected live build/access/repeat acceptance and evidence.
4. Continue remaining M4/core/M5 atomic units with usage checkpoints. Required comprehensive
   governance audit follows full Phase 3 verification, before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Products acceptance 7a2e1e6 and implementation 5640124 published.
- Orders implementation 418c30f published; acceptance checkpoint is containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Confirm actual cleanliness/publication.
- Last observed usage 48% five-hour / 47% weekly remaining; account-wide, not task reservation.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_orders
```

Use docs/customer-staging.md for retained regression commands and docs/order-staging.md
for orders. No secrets/raw records/driver diagnostics. Project-resource deletion requires
specific informed permission; legitimate application data deletion follows product/security rules.
