# CommerceLens work state

Authoritative handoff; verify actual Git/files on resume. Updated 2026-10-02.

## Project State

- Phase 3, Database/SQL/Analytics Engineering; M4 order-items staging implementation
  validated, live acceptance pending. Objective: tested analytical warehouse per master plan,
  ADR 0003 and Free/views-first choice. Phase 4 and comprehensive exit audit have not begun.
- At resume, roughly45-60% of Phase 3 warehouse effort remained: four staging sources,
  ten core models and M5 mart/queries/performance/reconstruction. Reasoned effort estimate,
  not elapsed-time prediction or a source-model-count percentage. Required audit follows.

## Completed Work

- Phases 1-2/professional-practices remediation complete; do not repeat them.
- M1 contracts, M2 isolated foundation and M3 landing complete: all9tables, 1,550,922 rows.
- Previously accepted staging: customers99,441/12tests, sellers3,095/11,
  category_translation71/8, products32,951/16, orders99,441/25. Counts are historical
  acceptance results; later child relationship tests may expand a parent selection.
- Orders checkpoint698191b published; products7a2e1e6 published. Parent order/product/seller
  read-only physical/access checks rerun today:3 passed. No discrepancy/partial work on resume.
- Items source-preserving model, exact money helper, 16dbttests, offline/native/physical
  checks and guide implemented/validated. Live item view not yet accepted.

## Files

- New dbt/macros/source_money.sql, dbt/models/staging/stg_order_items.sql/.yml;
  dbt/tests/stg_order_items_grain/lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_item_staging.py, test_warehouse_item_postgres_integration.py,
  test_warehouse_item_integration.py; docs/item-staging.md.
- Modified src/warehouse/dbt_runner.py (only approved item selector) and WORK_STATE.md.
- Existing bigint/timestamp macros unchanged. No files deleted/renamed or dependencies changed.
  Ignored UUID test/dbt artifacts retained; scratch candidate copies are not build inputs.

## Technical Decisions

- Item grain(order_id,order_item_id), all7sourcefields plus lineage; no aggregation/parentjoin.
  Positive signed64 sequence via existing exact guarded helper; literal lowercase source IDs,
  mandatory reference tests target accepted order/product/seller views. Empty becomes NULL.
- Money numeric(18,2) matches M3 source.py parse_money: ASCII nonnegative digits, optional1-2
  decimals; no signs/exponents/whitespace/extra scale/nonfinite/overflow or Float64/rounding.
  Guard text before numeric casts, bound9999999999999999.99 before typmod; zero remains valid.
- Shipping timestamp uses existing strict canonical/calendar/nswhole-second helper and remains
  withouttimezone. Invalid/mandatorymissing values retained as typedNULL and block acceptance.
- Contextual shipping-before-purchase/over365-day flags belong fact_order_items; four historical
  over365-day rows must be preserved/flagged there. No duration/KPI/eligibility change.
- Dedicated restricted transformer/verify-full TLS. Compatible CREATE OR REPLACE retains
  identity/owner/grants; view commits before tests. Failed acceptance is not rollback.
- No source load, migration, account, paid resource, credential or application changes.
- Recommended deferred Phase2 parser compatibility debt: pandas accepts nonpadded dates,
  leap-second rollover and dynamicnow/today. Strict warehouse guard mitigates currentverified
  source. Ownerprojectmaintainer; fix before accepting a different source version.

## Validation

- Ruff lint/format passed (87 files); mypy passed22implementationfiles.
- Offline dbt parse passed; retained artifact .artifacts/dbt/2a1d244cac56472081eb26fb11e5b15a.
- Warehouse/API regression 463 passed/221 deliberate opt-in live skips;
  known AnyIO warning. Native readonly item SQL cases 83 passed: exact money grammar,
  range/scale/cent sums, sequence/date boundaries, missingness, grain/reference/inline casts.
- Orders/products/sellers parent physical/access checks3 passed today.
- Item first/repeat/physical acceptance: Not yet tested. Sourceexpected112,650 rows;
  exact technical price/freight sums13591643.70/2251909.54, not business metric definitions.
- Staged contents/history secret scans required at checkpoint/publication.
- Existing full source/frontend/advisory pass2026-09-22 remains historical; not rerun for
  this dependency-unchanged data-only unit. Full check.ps1 cleanup needs approval/adaptation.
- No deployment, E2E or comprehensive post-Phase3 governance audit this session.

## Current Repository Condition

PARTIALLY IMPLEMENTED / SAFE TO RESUME. Five staging sources accepted; item code validated
but actual view acceptance pending. No current known failing tests. Verify actual Git status.

## Incomplete Work

- Item selected first build, physical/access, repeat rows/exactmoney/identity/storage/evidence.
  Then order_payments, order_reviews, geolocation staging; ten core models and M5 pending.
- Shipping context flags explicit M4/core gate; parser debt/newsource gate; audit E01-E10
  retain revisit gates. Required comprehensive governance gate after full Phase3 verification.

## Exact Next Actions

1. Check allowance/status/history; confirm this validated implementation checkpoint and scans.
2. Run selected dbt-build --select stg_order_items; verify one view/16tests. On failure retain
   artifacts/view, record failure and diagnose; no drop/fullrefresh/reload.
3. Run only the item physical module with COMMERCE_WAREHOUSE_ITEM_INTEGRATION=1, then bounded
   repeat acceptance:112,650 rows, exact independent price/freight sums, OID/owner/grants and
   storage<400M bytes. Store aggregate docs/item-staging-verification.json.
4. Update guide/phase-plan/selected-model links/handoff, scan/commit/push and confirmclean
   branch before next atomic unit. Recheck usage. No comprehensive audit during unfinishedphase.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Lastpublished698191b.
- Item implementation checkpoint is containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
  Verify actual cleanliness/publication. No partially completed changes inherited at resume.
- Usage observed at resume99%five-hour/47%weekly remaining; account-wide, not task reservation.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_items
```

Use docs/customer-staging.md retained test commands and docs/item-staging.md. Never output
secrets/source records/driver diagnostics. Project resource deletion needs informed approval;
legitimate application data deletion follows product security/ownership/integrity rules.
