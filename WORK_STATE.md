# CommerceLens work state

Authoritative handoff; verify actual repository, Git and documentation on resume.
Updated 2026-10-03. No knowledge required for continuation should depend on chat alone.

## Project State

- Phase 3 Database/SQL/Analytics Engineering. M4 review staging
  COMPLETE; next source geolocation.
- Current task: geolocation implementation/offline/native gates COMPLETE; live acceptance PENDING.
  Resume baseline was clean published 177c71d; no interrupted source changes.
  Approved cleanup complete: A/B/D old outputs removed; C and preserved drafts retained.
  Selected first build, physical/access and repeat acceptance not yet run.
- Objective: tested analytical warehouse per master plan and ADR 0003, Free/views-first
  ADR 0004. Phase 4 and the comprehensive exit governance audit have not begun.
- Approximately 40-50% of Phase 3 warehouse implementation/verification effort remains
  after review acceptance. This is a reasoned estimate, not a time forecast or
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
  focused offline/native/physical test modules and guide COMPLETE; all 99,224 rows retained.

## Files

- New stg_geolocation.sql/.yml and three singular lineage/domain/reconciliation tests;
  offline/native/physical geolocation test modules and docs/geolocation-staging.md.
- Modified src/warehouse/dbt_runner.py approved selector; no helper, dependency,
  migration, source-data or application changes. No project resources deleted in this unit.

- Updated docs/cleanup-review-2026-10-02.md, cleanup-proposal-2026-10-02.json and this handoff.
- Deleted only the approved 28 ignored A/B/D roots (43,967 files, 784.75 MiB); full paths
  remain recorded in the review/proposal. C's duplicate dataset download retained.
- Ignored .artifacts/cleanup-preserved-20261002 retains three exact historical drafts,
  hash manifest and per-root cleanup execution journal; this backup was not removed.

- New dbt/models/staging/stg_order_reviews.sql/.yml;
  dbt/tests/stg_order_reviews_grain/lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_review_staging.py, test_warehouse_review_postgres_integration.py,
  test_warehouse_review_integration.py; docs/review-staging.md and verification JSON.
- Modified approved selectors in src/warehouse/dbt_runner.py, WORK_STATE.md
  and phase-3-plan.md/customer-staging.md status/selector guidance.
- Existing source_numeric/source_timestamp/source_money helpers and source unchanged.
  No migration, dependencies, raw data, credentials or application changes. Current UUID
  dbt acceptance artifacts retained; approved historical test output removed in cleanup.

## Technical Decisions

- Geolocation preserves all observations/exact duplicates with load/ordinal lineage;
  ZIP is not unique. Literal one-to-five ASCII-digit ZIP/city/state text, guarded double
  coordinate types and global range checks preserve existing contracts. Broad-Brazil
  warning uses inclusive lat[-34,6]/lng[-74,-28], false if either typed coordinate absent.
  No canonical coordinate, row filtering or duplicate ZIP-to-order join introduced.

- Owner approved A/B removal, retained C and delegated D: remove old generated D output
  because current runners recreate fresh fixtures/targets. Approval is limited to this
  exact batch, not future automatic cleanup. No tracked source or accepted warehouse evidence removed.

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

- Geolocation focused offline 134 passed; Ruff lint/format 100 files and mypy 22
  implementation files passed. Warehouse/API regression 701 passed / 381 opt-in skips;
  known AnyIO deprecation warning. Offline parse passed: .artifacts/dbt/8cd0a32fc01c4bebba797a8b9cc3a7ed.
- Initial native run: 71 passed / 1 high-precision equality failed. Diagnosis proved
  extra_float_digits=0 shortened text results; binary fetch and float8send exactly
  match the independent expected binary64 value. Model/helper unchanged; native
  projection now reads binary results with strict assertions. Rerun: all 72 passed.

- Cleanup COMPLETE: approved 28 roots revalidated (containment, links, use, sizes),
  removed and confirmed absent. 858 retained files hash-unchanged. All nine canonical
  CSVs and nine retained C copies passed manifest size/SHA-256 checks after removal;
  three preserved draft hashes passed. Active environments/Git/evidence/tools retained.
- No tests/builds/database actions ran for unchanged source/configuration in cleanup;
  earlier Phase 3 results below remain their actual historical run results. Cleanup
  diff/complete staged-contents/history secret checks passed before the checkpoint.

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
- Review first/repeat each passed one view / 14 dbt tests; actual-login physical/access passed.
  Raw/view 99,224 rows; missing title/message 87,656 / 58,247; zero reversed answers,
  547 orders with multiple reviews. Repeat identity/owner/grants preserved, password absent
  from retained artifacts; database 287141011 bytes <400M.
  Evidence docs/review-staging-verification.json; these observations do not define KPIs.

## Current Repository Condition

STABLE / SAFE TO RESUME. Eight staging sources accepted. Geolocation code/offline/native
gates COMPLETE; first live build/access/repeat acceptance pending. Phase 3 incomplete.
No current known failed tests; verify actual Git status.

## Incomplete Work

- Recommended API coordinate transport gate: current dev session extra_float_digits=0
  rounds text results; use binary fetch or reviewed positive session output setting
  before exposing precise coordinate reads. Warehouse values/reconciliation are correct.

- Stale progress/test-location documentation wording recorded in cleanup review;
  correct it during maintenance, retaining all historical documents. No cleanup decision
  remains pending; C is intentionally retained as the owner's offline fallback.

- Geolocation staging; five dimensions, int_order_customers and four facts remain pending.
- M5: technical order-component mart, example SQL, performance/query-plan and
  reconstruction/recovery proofs. Shipping context/core and multiple-review aggregate gates.
- Parser compatibility debt before a new source; audit E01-E10 revisit gates remain.
  Full governance audit/corrections required after verified Phase 3, before Phase 4.

## Exact Next Actions

1. Confirm a clean code checkpoint; check current database size <400,000,000 bytes,
   then selected dbt-build --select stg_geolocation using protected transformer settings.
2. Run the opt-in geolocation physical/access test, then compatible selected repeat build;
   verify OID/owner/grants, all 1,000,163 rows, 19,015 ZIPs, 261,831 duplicate observations,
   31 warning flags and no password in artifacts. Preserve failed artifacts/view; no drop.
3. Record actual acceptance evidence/checkpoint, then core dimensions/intermediate/facts
   and M5. No reload/reprovision/migration replay or repeat accepted source implementation.
4. Comprehensive governance audit only after verified Phase 3, before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Payment acceptance 7d8ffb6 published.
- Review implementation a63c7ca / acceptance 484249b published.
- Cleanup execution checkpoint 177c71d published; pre-deletion assessment 0096260.
- Geolocation code checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Verify actual clean/synced status.
- Latest recorded allowance 99% five-hour / 100% weekly remaining; account-wide,
  not a task/model reservation. Recheck before substantial units. No reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_geolocation
```

Use customer-staging.md retained regression instructions and geolocation-staging.md.
Never print secrets/source records/driver diagnostics. Project-resource deletion requires
informed explicit approval; legitimate product data deletion follows authorization,
ownership, confirmation and integrity requirements. No paid changes or reset credits used.
