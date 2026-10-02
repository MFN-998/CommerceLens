# CommerceLens work state

Authoritative handoff; verify actual repository, Git and documentation on resume.
Updated 2026-10-02. No knowledge required for continuation should depend on chat alone.

## Project State

- Phase 3 Database/SQL/Analytics Engineering. M4 payment implementation validated; live acceptance pending.
- Objective: tested analytical warehouse per master plan, ADR 0003 and Free/views-first
  ADR 0004. Phase 4 and comprehensive exit governance audit have not begun.
- Approximately 40-55% of warehouse implementation/verification effort remains after item acceptance.
  This is a reasoned range, not a time forecast or a staging-model-count percentage.
  Additional exit audit/correction effort cannot be known until that later gate runs.

## Completed Work

- Phases 1-2 and their professional-practices remediation complete; do not repeat them.
- M1 contracts, M2 isolated foundation and M3 all-nine-table landing complete:
  1,550,922 rows. No raw reload, migration replay or account reprovisioning needed.
- Accepted staging: customers 99,441 / 12 tests, sellers 3,095 / 11,
  category translation 71 / 8, products 32,951 / 16, orders 99,441 / 25,
  items 112,650 / 16. Historical checkpoint test counts; later child relationships
  can expand parent selections through dbt eager indirect test selection.
- Orders acceptance 698191b; items implementation 923f058 / acceptance 05dc235 published.
  Order/product/seller physical/access checks rerun today: 3 passed.
- Payments source-preserving model, three quality flags, 16 dbt data tests,
  focused offline/native/physical tests and guide saved and validated.

## Files

- New dbt/models/staging/stg_order_payments.sql/.yml;
  dbt/tests/stg_order_payments_grain/lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_payment_staging.py, test_warehouse_payment_postgres_integration.py,
  test_warehouse_payment_integration.py; docs/payment-staging.md.
- Modified src/warehouse/dbt_runner.py (approved payment selector), WORK_STATE.md
  (baseline and exact continuation).
- Accepted item money helper and existing bigint/timestamp helpers unchanged.
  No resource deletion/rename, dependencies, migration, credentials, raw data or application changes.
  Ignored UUID dbt/pytest artifacts retained; scratch candidates are not runtime inputs.

## Technical Decisions

- Payment grain (order_id,payment_sequential), five source fields plus immutable lineage,
  three independent booleans; no aggregation/parent join/row filtering. Literal source
  methods restricted to credit_card/boleto/voucher/debit_card/not_defined.
- Positive exact signed-64-bit payment sequence; nonnegative exact installments.
  Payment numeric(18,2) from original raw decimal text matches M3: ASCII nonnegative
  digits, optional 1-2 decimals, <=9999999999999999.99; no sign/exponent/whitespace,
  extra scale, Float64 intermediate or rounding. Existing guarded helpers reused.
- Missing/rejected mandatory values become typed NULL and block acceptance. Zero/undefined
  observations retained and flagged; numeric NULL yields false zero flags, while literal
  not_defined stays flagged independently. No repair, eligibility or KPI policy invented.
- Item shipping-before-purchase/over-365-day context flags remain explicit fact_order_items
  M4 gate, including four historical over-one-year rows. Durations need valid ordered events.
- Restricted transformer, verify-full TLS, private warehouse/API denied. Compatible
  CREATE OR REPLACE preserves view identity/owner/grants. View commit precedes tests;
  a failed test is failed acceptance, not rollback. Preserve artifacts and diagnose.
- Recommended deferred Phase 2 parser compatibility debt: pandas accepts nonpadded dates,
  leap-second rollover and dynamic now/today. Strict warehouse guard mitigates current
  verified source. Owner: maintainer; fix before accepting a different source version.

## Validation

- Ruff lint/format passed (91 Python files); mypy passed 22 implementation files.
- Offline dbt parse passed; retained artifact .artifacts/dbt/0a382d560bb04a26a31abe2dc9135458.
- Warehouse/API regression 533 passed / 263 deliberate opt-in skips;
  known AnyIO deprecation warning only. Focused native read-only payment cases 41 passed.
- Accepted item first/repeat each one view / 16 tests; native 83 passed, physical/access passed,
  exact price/freight sums 13591643.70 / 2251909.54; 112,650 retained rows,
  identity/owner/grants preserved and password absent from artifacts.
- Payment first/repeat builds and actual-login physical/access acceptance: Not yet tested.
- Complete staged contents/history secret scans required before each checkpoint/publication.
  Published item code/acceptance scans passed; payment results are recorded with its commits.
- Full source/frontend/advisory gate last passed 2026-09-22; not rerun for unchanged
  dependencies/data-only work. Full check.ps1 cleanup requires approval/adaptation.
- No deployment, E2E or comprehensive post-Phase 3 audit this session.

## Current Repository Condition

PARTIALLY IMPLEMENTED / SAFE TO RESUME. Six staging sources accepted; payment code validated, live acceptance pending.
Phase 3 incomplete. No current known failed tests; verify actual Git status.

## Incomplete Work

- Payment selected first build, actual-login physical/access, repeat rows/exact sum/flags,
  identity/storage/secret-free evidence and acceptance publication.
- Then order_reviews/geolocation staging, ten core models and M5 remain pending.
- Core: five dimensions, int_order_customers and four facts. M5: technical order-component
  mart, example SQL, performance/query-plan and reconstruction/recovery verification.
- Shipping context/core gate, parser debt/new-source gate, audit E01-E10 revisit gates
  remain documented. Comprehensive governance/corrections required before Phase 4.

## Exact Next Actions

1. Inspect allowance/status/history and confirm containing validated code checkpoint published.
2. Run selected dbt-build --select stg_order_payments; expect one view / 16 tests.
   If acceptance fails retain view/artifacts and diagnose; no drop/full refresh/raw reload.
3. Run only tests/test_warehouse_payment_integration.py with
   COMMERCE_WAREHOUSE_PAYMENT_INTEGRATION=1, then bounded repeat verification:
   103,886 rows, exact sum 16008872.12, flags 2/9/3, OID/owner/grants and database <400M.
   Store aggregate docs/payment-staging-verification.json.
4. Update guide/phase-plan/selected-model links/handoff, scan/commit/push; confirm clean.
   Recheck usage before next atomic source. No comprehensive audit during unfinished Phase 3.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Last accepted published 05dc235.
- Payment code checkpoint is the containing commit; inspect actual publication/status.
  Resolve: git log -1 --format="%H %s" -- WORK_STATE.md. Verify actual clean/synced status.
- Latest observed allowance 77% five-hour / 43% weekly remaining; account-wide,
  not a task/model reservation. Recheck before another substantial unit.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_payments
```

Use docs/customer-staging.md retained regression instructions and docs/payment-staging.md.
Never print secrets/source records/driver diagnostics. Project-resource deletion requires
informed explicit approval; legitimate product data deletion follows authorization,
ownership, confirmation and integrity requirements. No reset credits or paid changes used.
