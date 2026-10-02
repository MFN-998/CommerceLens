# CommerceLens work state

Authoritative handoff; verify actual Git/files on resume. Updated 2026-10-02.

## Project State

- Phase 3, Database/SQL/Analytics Engineering; M4 order-items staging COMPLETE; next source order_payments.
  Objective: tested analytical warehouse per master plan,
  ADR 0003 and Free/views-first choice. Phase 4 and comprehensive exit audit have not begun.
- At resume, roughly 45-60% of Phase 3 warehouse effort remained: four staging sources,
  ten core models and M5 mart/queries/performance/reconstruction. Reasoned effort estimate,
  not elapsed-time prediction or a source-model-count percentage. Required audit follows.

## Completed Work

- Phases 1-2/professional-practices remediation complete; do not repeat them.
- M1 contracts, M2 isolated foundation and M3 landing complete: all nine tables, 1,550,922 rows.
- Previously accepted staging: customers 99,441 / 12 tests, sellers 3,095 / 11,
  category_translation 71 / 8, products 32,951 / 16, orders 99,441 / 25. Counts are historical
  acceptance results; later child relationship tests may expand a parent selection.
- Orders checkpoint 698191b published; products 7a2e1e6 published. Parent order/product/seller
  read-only physical/access checks rerun today: 3 passed. No discrepancy/partial work on resume.
- Items source-preserving model, exact money helper, 16 dbt tests, offline/native/physical
  checks and guide COMPLETE. All 112,650 item rows and exact source money retained.

## Files

- New dbt/macros/source_money.sql, dbt/models/staging/stg_order_items.sql/.yml;
  dbt/tests/stg_order_items_grain/lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_item_staging.py, test_warehouse_item_postgres_integration.py,
  test_warehouse_item_integration.py; docs/item-staging.md and verification JSON.
- Modified src/warehouse/dbt_runner.py (only approved item selector), WORK_STATE.md,
  docs/phase-3-plan.md and docs/customer-staging.md (current status/selector links).
- Existing bigint/timestamp macros unchanged. No files deleted/renamed or dependencies changed.
  Ignored UUID test/dbt artifacts retained; scratch candidate copies are not build inputs.

## Technical Decisions

- Item grain(order_id,order_item_id), all seven source fields plus lineage; no aggregation or parent join.
  Positive signed-64-bit sequence via existing exact guarded helper; literal lowercase source IDs,
  mandatory reference tests target accepted order/product/seller views. Empty becomes NULL.
- Money numeric(18,2) matches M3 source.py parse_money: ASCII nonnegative digits, optional 1-2
  decimals; no signs/exponents/whitespace/extra scale/nonfinite/overflow or Float64/rounding.
  Guard text before numeric casts, bound 9999999999999999.99 before typmod; zero remains valid.
- Shipping timestamp uses existing strict canonical/calendar/nanosecond-compatible whole-second helper and remains
  without time zone. Invalid/mandatory missing values retained as typed NULL and block acceptance.
- Contextual shipping-before-purchase/over-365-day flags belong fact_order_items; four historical
  over-365-day rows must be preserved/flagged there. No duration/KPI/eligibility change.
- Dedicated restricted transformer/verify-full TLS. Compatible CREATE OR REPLACE retains
  identity/owner/grants; view commits before tests. Failed acceptance is not rollback.
- No source load, migration, account, paid resource, credential or application changes.
- Recommended deferred Phase 2 parser compatibility debt: pandas accepts nonpadded dates,
  leap-second rollover and dynamic now/today. Strict warehouse guard mitigates current verified
  source. Owner: project maintainer; fix before accepting a different source version.

## Validation

- Ruff lint/format passed (87 files); mypy passed 22 implementation files.
- Offline dbt parse passed; retained artifact .artifacts/dbt/2a1d244cac56472081eb26fb11e5b15a.
- Warehouse/API regression 463 passed/221 deliberate opt-in live skips;
  known AnyIO warning. Native readonly item SQL cases 83 passed: exact money grammar,
  range/scale/cent sums, sequence/date boundaries, missingness, grain/reference/inline casts.
- Orders/products/sellers parent physical/access checks: 3 passed today.
- Item first/repeat each passed one view / 16 tests; actual-login physical/access passed.
  Raw/view: 112,650 rows; exact independent price/freight sums 13591643.70 / 2251909.54.
  Repeat OID/owner/grants preserved; password absent from first/repeat artifacts.
  Database bytes 287124627 <400M; evidence docs/item-staging-verification.json.
  These sums are technical source reconciliation, not business metrics.
- Complete staged contents/history scans passed for published implementation 923f058.
  Acceptance publication requires the same staged/history scans.
- Existing full source/frontend/advisory pass2026-09-22 remains historical; not rerun for
  this dependency-unchanged data-only unit. Full check.ps1 cleanup needs approval/adaptation.
- No deployment, E2E or comprehensive post-Phase 3 governance audit this session.

## Current Repository Condition

STABLE / SAFE TO RESUME. Item atomic unit COMPLETE, six of nine staging sources accepted.
Phase 3 incomplete; no current known failed tests/partial model. Verify actual Git status.

## Incomplete Work

- order_payments, order_reviews, geolocation staging; ten core models and M5 pending.
  Roughly40-55% of Phase 3 warehouse effort remains; comprehensive audit gate follows.
- Shipping context flags explicit M4/core gate; parser debt/newsource gate; audit E01-E10
  retain revisit gates. Required comprehensive governance gate after full Phase 3 verification.

## Exact Next Actions

1. Read docs/item-staging.md/evidence; inspect Git/allowance and confirm containing checkpoint
   published/clean. Do not redo accepted models, migrations, raw loads or Phases 1-2.
2. Read TABLES["order_payments"], payment warning/domains in src/validation/profile.py,
   ADR0003 and the now-accepted source_money helper. Prepare stg_order_payments at
   (order_id,payment_sequential): exact amount, literal method, zero/undefined flags,
   positive sequence/nonnegative installments and mandatory order reference.
3. Verify/checkpoint code, then selected first/physical/repeat acceptance with exact source
   amount reconciliation. Continue remaining M4/core/M5 units with usage checkpoints.
4. Full governance audit runs only after Phase 3 complete/verified and before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Item implementation 923f058
  published; acceptance checkpoint is containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
  Verify actual cleanliness/publication. No partially completed changes inherited at resume.
- Usage last observed 80% five-hour / 44% weekly remaining; account-wide, not task reservation.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_order_items
```

Use docs/customer-staging.md retained test commands and docs/item-staging.md. Never output
secrets/source records/driver diagnostics. Project resource deletion needs informed approval;
legitimate application data deletion follows product security/ownership/integrity rules.
Item live first build passed 2026-10-02; artifact .artifacts/dbt/426dfeb262884bf99ad1b2c1bcbc3ed7. Database before build287116435 bytes. Implementation923f058 published; physical/access and repeat acceptance still pending. No deletion/reload. Latest allowance80%five-hour / 44% weekly remaining.
