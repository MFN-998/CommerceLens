# CommerceLens work state

Authoritative handoff; verify actual repository, Git and documentation on resume.
Updated 2026-10-02. No knowledge required for continuation should depend on chat alone.

## Project State

- Phase 3 Database/SQL/Analytics Engineering. M4 review staging
  implementation validated; live acceptance pending.
- Objective: tested analytical warehouse per master plan and ADR 0003, Free/views-first
  ADR 0004. Phase 4 and the comprehensive exit governance audit have not begun.
- Approximately 40-50% of Phase 3 warehouse implementation/verification effort remains
  after payment acceptance. This is a reasoned estimate, not a time forecast or
  staging-model-count percentage. Required later audit/correction effort remains unknown.

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
- Payments implementation 0a1dbb4 / acceptance 7d8ffb6 published: 103,886 rows,
  16 dbt tests, native 41 cases, physical/access passed; zero/undefined values retained.
- Review source-preserving composite model, optional text, reversal flag, 14 dbt tests,
  focused offline/native/physical test modules and guide implemented/validated; live pending.

## Files

- New dbt/models/staging/stg_order_reviews.sql/.yml;
  dbt/tests/stg_order_reviews_grain/lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_review_staging.py, test_warehouse_review_postgres_integration.py,
  test_warehouse_review_integration.py; docs/review-staging.md.
- Modified approved selectors in src/warehouse/dbt_runner.py, WORK_STATE.md
  (current baseline/continuation).
- Existing source_numeric/source_timestamp/source_money helpers unchanged. No resource
  deletion/rename, migration, dependencies, raw data, credentials or application changes.
  Ignored UUID test/dbt artifacts retained; scratch candidates are not runtime inputs.

## Technical Decisions

- Reviews retain (review_id,order_id), seven source fields plus lineage; optional exact-empty
  title/message become NULL, otherwise Unicode/newlines/whitespace/markup remain literal.
  Never render untrusted review content as application HTML later. No selected review/join/filter.
- Score exact bigint 1-5. Creation/answer strict canonical source timestamps without time zone.
  Reversal flag preserves valid backward events; missing/invalid typed dates give false and
  mandatory validation failure. Multiple-review counts belong later core/mart (547 orders).
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

- Ruff lint/format passed (95 Python files); mypy passed 22 implementation files.
- Offline dbt parse passed; retained artifact .artifacts/dbt/fbe16a3c48c14300912d0855588fa485.
- Warehouse/API regression 620 passed / 308 deliberate opt-in skips;
  known AnyIO deprecation warning only. Native read-only review cases 44 passed.
- Accepted item first/repeat each one view / 16 tests; native 83 passed, physical/access passed,
  exact price/freight sums 13591643.70 / 2251909.54; 112,650 retained rows,
  identity/owner/grants preserved and password absent from artifacts.
- Payment first/repeat each passed one view and 16 dbt tests; actual-login physical/access
  check passed. Raw/view 103,886 rows and exact payment sum 16008872.12; quality counts
  2 zero installments / 9 zero amounts / 3 undefined methods. Identity/owner/grants preserved;
  password absent from first/repeat artifacts. Database 287132819 bytes <400M.
  Evidence docs/payment-staging-verification.json; sums are technical reconciliation only.
- Complete staged contents/history secret scans required before each checkpoint/publication.
  Published item code/acceptance scans passed; payment results are recorded with its commits.
- Full source/frontend/advisory gate last passed 2026-09-22; not rerun for unchanged
  dependencies/data-only work. Full check.ps1 cleanup requires approval/adaptation.
- No deployment, E2E or comprehensive post-Phase 3 audit this session.
- Review first/repeat/physical acceptance: Not yet tested.

## Current Repository Condition

PARTIALLY IMPLEMENTED / SAFE TO RESUME. Seven sources accepted; review code validated, live pending.
Phase 3 incomplete. No current known failed tests; verify actual Git status.

## Incomplete Work

- Review selected first build, actual-login physical/access and repeat
  identity/count/text/reversal/storage/secret-free evidence and acceptance publication.
- Geolocation staging; five dimensions, int_order_customers and four facts remain pending.
- M5: technical order-component mart, example SQL, performance/query-plan and
  reconstruction/recovery proofs. Shipping context/core and multiple-review aggregate gates.
- Parser compatibility debt before a new source; audit E01-E10 revisit gates remain.
  Full governance audit/corrections required after verified Phase 3, before Phase 4.

## Exact Next Actions

1. Inspect allowance/Git/history and confirm containing validated review code checkpoint published.
2. Run selected dbt-build --select stg_order_reviews; expect one view / 14 tests.
   On failure retain artifacts/view and diagnose; no drop/full refresh/raw reload.
3. Run only review physical module with COMMERCE_WAREHOUSE_REVIEW_INTEGRATION=1,
   then bounded repeat: 99,224 rows; optional-null counts 87,656/58,247; reversal0,
   multiple-review orders547; OID/owner/grants, database <400M and secret-free artifacts.
4. Save aggregate review evidence, update guide/phase plan/selector links/handoff, scan,
   commit/push and confirm clean; recheck allowance before geolocation. No premature audit.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Payment acceptance 7d8ffb6 published.
- Review implementation checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Verify actual clean/synced status.
- Latest recorded allowance 55% five-hour / 40% weekly remaining; account-wide,
  not a task/model reservation. Recheck before substantial units. No reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_reviews
```

Use customer-staging.md retained regression instructions and review-staging.md.
Never print secrets/source records/driver diagnostics. Project-resource deletion requires
informed explicit approval; legitimate product data deletion follows authorization,
ownership, confirmation and integrity requirements. No paid changes or reset credits used.
