# CommerceLens work state

Updated: 2026-10-01. Repository: `D:\My Projects\CommerceLens`.
Read AGENTS, master plan, engineering standards, execution protocol and deletion-and-governance.

## Project State

- Phases 1–2 and their audit COMPLETE; Phase 3 M1–M3 COMPLETE, M4 IN PROGRESS, M5 pending.
- Current milestone: customer/seller/category/product staging COMPLETE / SAFE TO RESUME.
- Current task: checkpoint/publish product acceptance; next source unit is orders staging.
- Objective remains a tested analytical warehouse. No Phase 4 or full exit governance audit yet.
- Allowance at resume 99% five-hour / 55% weekly; last observed 72% / 51%. Recheck before
  beginning another substantial unit; preserve this verified checkpoint as usage becomes limited.

## Completed Work

- Recovered clean b7ec0bb; no partial edits. Read-only existing three views recheck: 3 passed.
- Added typed product view retaining all 32,951 rows and all source attributes/lineage.
- Added eight source missingness flags plus zero-weight flag; no filtering/imputation/translation join.
- Added guarded bigint/double macros, 16 dbt tests, 57 local synthetic and 31 native cases,
  actual-login physical/type/access acceptance and complete multiset reconciliation.
- Fixed planner-time unsafe constant cast found by native tests; added dedicated regression.
  Per-case savepoints prevent one SQL error from poisoning later cases.
- First and repeat live product builds passed; expected nine flag counts verified against
  Phase 2 observations. View identity/owner/grants preserved. No source reload or account setup.

## Files

- Created dbt/macros/source_numeric.sql; dbt/models/staging/stg_products.sql/yml;
  dbt/tests/stg_products_{lineage_unique,source_domains,source_reconciliation}.sql;
  tests/test_warehouse_product_{staging,integration,postgres_integration}.py;
  docs/product-staging.md and docs/product-staging-verification.json.
- Modified approved selector in src/warehouse/dbt_runner.py, customer guide, Phase 3 plan
  and this handoff. No tracked files deleted/renamed, dependencies/migrations/credentials changed.
- Scratch candidates remain outside the actual repo and are not active source inputs; do not
  re-adopt them. No resource deletion this session; prior six scan-copy approval already completed.

## Technical Decisions

- Preserve original product column names, literal category and lineage. Exact empty becomes
  NULL. Three nullable count/lengths become bigint without float intermediates or rounding;
  four nullable physical attributes become double precision. Nonnegative domains permit zero.
- Missing flags reflect raw missingness, not failed numeric casts. Nonempty unrepresentable
  values remain as typed NULL and fail a blocking aggregate source-domain test. Raw is immutable.
- Guard text before immutable casts to avoid planning errors. Grammar/PG representability
  accepts decimal/scientific input; signed64 and integrality checked exactly. PG float underflow
  and some Unicode whitespace differ from pandas; explicit failure instead of fabricated zero.
- No translation join here: dim_product will separately flag missing translation coverage.
- Free plan views-first; raw/database ceilings 367M/400M bytes. Existing CREATE OR REPLACE
  materialization preserves objects; incompatible changes fail. View commit precedes data tests;
  failed acceptance does not imply automatic rollback.
- Selected runner approves only customer/seller/category/products; dedicated transformer,
  verify-full TLS, retained UUID artifacts, no telemetry/file logs/failure record storage.
- Project-resource deletion requires informed approval; legitimate product deletion follows
  authorization/integrity rules. Full check.ps1 cleanup needs permission/adaptation.

## Validation

- Ruff lint/format: 79 files passed. Mypy: 22 implementation files passed.
- Final warehouse/API regression: 241 passed, 49 deliberately skipped live tests; known AnyIO warning.
- Native read-only product checks: 31 passed, including signed64 boundaries, fractional integers,
  malformed/nonfinite/overflow/underflow inputs, source flags and inline-constant planning regression.
- Initial native run failed extreme-exponent planning, followed by aborted-transaction cascades;
  diagnosis and guarded operands/savepoint isolation fixed it. No unresolved failure remains.
- First/repeat product dbt builds each passed 16 tests and one view; 32,951 raw/staging rows.
- Actual-login read-only physical/access acceptance passed. Repeat owner/OID/grants unchanged;
  password absent from repeat artifacts. Evidence JSON records storage and exact test statuses.
- Product flag counts: 610 each missing category/name length/description length/photos;
  2 each missing weight/length/height/width; 4 zero weights. Warnings overlap; no repair.
- Customer/seller/category previous acceptance remains 99,441/3,095/71 rows and 12/11/8 tests.
- M3 nine-table load remains 1,550,922 rows; no rerun needed. No empty-target live tests on populated DB.
- Complete staged code contents secret scan passed before 5640124. Final docs/history scans
  and publication are checkpoint gates. No new scan export archives created.
- Full source/frontend/advisory gate not rerun; prior historical pass 2026-09-22. No dependency
  changes, deployment, E2E or comprehensive post-Phase-3 audit this session.

## Current Repository Condition

STABLE / SAFE TO RESUME. Implementation 5640124 and the containing acceptance checkpoint
record completed product staging. No known failing current checks or partial model implementation.
Verify actual Git cleanliness/publication on resume.

## Incomplete Work

- Five staging sources: orders, order_items, order_payments, order_reviews, geolocation.
  Then core dimensions/facts/tests, M5 marts/technical queries, performance/reconstruction checks.
- Existing full check.ps1 cleanup needs permission or a reviewed retained alternative.
- Audit E01–E10 retain revisit gates. Complete/verify all Phase 3, then full governance audit,
  required corrections/regression before Phase 4. No premature comprehensive audit.

## Exact Next Actions

1. Check allowance/status/history; read product guide/evidence. Confirm containing checkpoint
   published and tree clean. Do not repeat completed models, raw load, migrations or accounts.
2. Read TABLES["orders"] in src/validation/contracts.py, src/cleaning/staging.py timestamp
   parsing and src/validation/profile.py lifecycle warnings, plus ADR 0003. Prepare stg_orders:
   preserve status/events/order/customer keys, timestamp-without-timezone types and explicit
   missing/reversed lifecycle flags. Treat warning anomalies as retained rows.
3. Add grain/reference/domain/full-row reconciliation and meaningful native synthetic tests.
   Validate/checkpoint, then selected live build/access/repeat acceptance and evidence.
4. Continue remaining M4/M5 units; required governance gate follows full Phase 3 verification.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Previous baseline b7ec0bb; product implementation 5640124.
- Final acceptance is containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
- Scan final staged contents/history; push feature branch and verify clean status at checkpoint.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_products
```

Use docs/customer-staging.md for retained regression commands and docs/product-staging.md
for product operation. Never print credentials, raw records or driver diagnostics.
