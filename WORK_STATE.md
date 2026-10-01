# CommerceLens work state

Authoritative handoff; verify actual Git/files on resume. No secrets or source records.
Updated 2026-10-01.

## Project State

- Current phase: Phase 3, Database/SQL/Analytics Engineering.
- Current milestone/task: M4 orders staging, validated implementation; live acceptance pending.
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
  25 dbt tests, offline/native and physical acceptance tests implemented. Actual view pending.
- Six previously approved obsolete local scan copies were removed earlier; no other approval.

## Files

- Created dbt/macros/source_timestamp.sql, dbt/models/staging/stg_orders.sql/.yml;
  dbt/tests/stg_orders_lineage_unique/source_domains/source_reconciliation.sql.
- Created tests/test_warehouse_order_staging.py, test_warehouse_order_integration.py,
  test_warehouse_order_postgres_integration.py and docs/order-staging.md.
- Modified src/warehouse/dbt_runner.py (only selected stg_orders addition) and WORK_STATE.md.
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
- Orders first build, physical/access acceptance and repeat: Not yet tested.
- Products first/repeat 16 tests, physical/access and 31 native cases accepted earlier today.
- Initial staged scan flagged checklist prose as a generic key; location/redacted prefix
  confirmed a false positive. Rephrased the checklist; no scanner rule disabled.
- Complete staged contents and history secret scans are checkpoint gates, not yet rerun
  for orders. Dependencies unchanged; full source/frontend/advisory gate last historical
  pass 2026-09-22, not rerun here because cleanup needs approval/adaptation.
- No deployment/E2E/full post-Phase-3 governance audit this session.

## Current Repository Condition

PARTIALLY IMPLEMENTED / SAFE TO RESUME. Orders code validated; live view not yet accepted.
No known current test failure. Four existing staging views remain accepted and functional.
Verify actual Git status and the containing implementation checkpoint before live work.

## Incomplete Work

- Verify the selected orders build, physical permissions and repeat-build row/flag counts;
  save acceptance evidence. Then four staging sources: items, payments, reviews, geolocation.
- Core dimensions/facts/tests and M5 technical marts/SQL/performance/reconstruction pending.
- Audit E01–E10 retain revisit gates; focused parser debt described above. Full check.ps1
  cleanup needs approval/adaptation. After all Phase 3 verified, perform required full
  governance audit/corrections/regression before Phase 4.

## Exact Next Actions

1. Check status/recent history/allowance; confirm the orders implementation checkpoint and
   complete staged/history scans. Do not repeat products or earlier units.
2. Run selected dbt-build --select stg_orders. It commits the view before its 25 tests.
   On failure preserve artifacts/view and record it; never drop/reload to conceal failure.
3. Enable only COMMERCE_WAREHOUSE_ORDER_INTEGRATION=1 for the physical module, then bounded
   repeat build: retain OID/owner/grants, 99,441 rows, flags, storage and secret-free evidence.
4. Update order guide, phase plan, selected-model guide and this handoff; scan/commit/push,
   confirm clean feature branch. Recheck usage before the next atomic source unit.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Last published acceptance 7a2e1e6; products implementation 5640124.
- Orders implementation checkpoint is containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Confirm actual cleanliness/publication.
- Last observed usage 61% five-hour / 49% weekly remaining; account-wide, not task reservation.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_orders
```

Use docs/customer-staging.md for retained regression commands and docs/order-staging.md
for orders. No secrets/raw records/driver diagnostics. Project-resource deletion requires
specific informed permission; legitimate application data deletion follows product/security rules.
