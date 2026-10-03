# CommerceLens work state

Authoritative handoff; reconcile actual repository/Git/documentation before resuming.
Updated 2026-10-03. Master plan, ADR 0003, engineering standards, execution and deletion
protocols apply. Synced project references and source datasets remain unchanged.

## Project State

- Phase 3 Database/SQL/Analytics Engineering, M4. All nine source staging views accepted.
- Customer identity COMPLETE, code/acceptance a93cb7f/dca21e9 published clean.
- Current unit: core.dim_product code/offline/native COMPLETE; first/physical/repeat
  live acceptance PENDING. No product dimension view built yet; source unchanged.
- Objective: tested analytical warehouse under Free/views-first ADR 0004; M4 and M5
  remain. Phase 4 and comprehensive exit audit have not begun.
- Active contract: dim_product, preserving 20 source fields and adding literal English
  translation/untranslated coverage (22 columns), per reviewed ADR 0003 contract.
- Roughly 30-40% of Phase 3 warehouse implementation/verification effort remains;
  broad reasoned range, not model count/time forecast. Later audit effort is unknown.

## Completed Work

- Phases 1-2 and retrospective professional remediation complete; do not repeat.
- M1 contracts/M2 isolated foundation/M3 exact landing complete: 1,550,922 rows.
  No reload, migration replay or account reprovisioning is needed.
- Accepted staging historical rows/tests: customers 99,441/12; sellers 3,095/11;
  category translation 71/8; products 32,951/16; orders 99,441/25; items 112,650/16;
  payments 103,886/16; reviews 99,224/14; geolocation 1,000,163/12. Later child tests
  can expand eager parent selection; these are evidence of their dated runs.
- Location: 19,177 ZIPs, 19,015 covered, 1,000,163 observations, 31 broad-box flags;
  8,556 city-ambiguous/8 state-ambiguous ZIPs. Joins retain 99,441/3,095 customer/seller
  rows and 278/7 uncovered rows. Geolocation retains 261,831 excess exact duplicates.
- Seller: all 3,095 IDs/rows and seven uncovered addresses/lineage retained.
- Customer: 96,096 literal identities; independent raw/stage/core membership matched.
  All 99,441 source/staging address/lineage records unchanged; no chosen current address.
- Approved cleanup A/B/D completed 177c71d; C dataset fallback/three drafts retained.
  New retained validation artifacts are not covered by that old deletion approval.

## Files

- New product unit: dim_product.sql/.yml, product_dimension_domains/source
  reconciliation tests, three product-dimension Python test modules and guide.
  Runner selector and phase/customer/product staging guides updated; no deletion.
- Created customer dim_customer.sql/.yml, two customer_dimension_* singular SQL tests,
  three tests/test_warehouse_customer_dimension*.py modules, customer-dimension.md
  and customer-dimension-verification.json. Runner approved selector updated.
- Modified phase-3/customer-staging guides, README and WORK_STATE. Handoff now summarizes
  dated historical evidence; full details remain in corresponding guides/JSON and Git.
- No files deleted/renamed, migrations/dependencies/credentials/source data/API/UI/deploy
  changes. All generated test/build artifacts retained ignored.
- Customer first/repeat artifacts: .artifacts/dbt/667f1a6e20dc417983048790727da2db
  and .artifacts/dbt/47f249e3864f411688d3e3d68ede3c78.
- Earlier baseline evidence: geolocation-staging-verification.json,
  location-dimension-verification.json and seller-dimension-verification.json in docs/.

## Technical Decisions

- dim_customer is ONLY customer_unique_id text DISTINCT with C collation. Repeating
  order-linked identities collapse at the declared identity grain; null/invalid IDs
  stay visible and block tests. Source addresses/load/ordinal are not chosen arbitrarily;
  later int_order_customers preserves them for fact_orders. No surrogate/counter/KPI.
- Four dbt tests: not-null, unique, ASCII lowercase32hex domain and full bidirectional
  EXCEPT ALL identity membership. Source/dimension duplicate semantics differ deliberately.
- Next dim_product: retain all staging fields/flags, literal category left join; nullable
  English plus is_untranslated_category distinguishes 610 missing/13 untranslated rows.
  Matched lookup with null English or duplicate keys blocks; no dedup/filter/fill labels.
- Private schemas/restricted transformer/verify-full TLS persist; no API exposure.
  Compatible CREATE OR REPLACE retains view identity/owner/grants. A view commits before
  tests, so failed acceptance is not rollback: preserve relation/artifacts and diagnose.
- Child reconciliation/relationships can expand eager parent tests. During bootstrap,
  build the new dimension before repeating parent tests that reference the pending view.
- ZIP remains literal one-to-five ASCII digits; no canonical geography or coordinate.
  Location counts/ambiguity describe observations only. Missing reference is a failure;
  legitimate uncovered geography is retained and flagged.
- extra_float_digits=0 rounds PostgreSQL text double output. Earlier binary fetch/
  float8send proved stored precision. Native projections with doubles use binary results;
  later precise API reads need binary transport or reviewed session output configuration.

## Validation

- Product code adopted after all three Python modules passed AST parsing;
  Initial focused124/lint116/mypy22/regression882/parse passed; native57 passed/2
  failed. Added missing-category/category consistency guard; removed an
  inappropriate domain assertion about exact English spelling, already
  protected by reconciliation. Added two offline regression cases.
  Final corrected checks: 126 focused passed; 884 warehouse/API regression passed
  /555 deliberate live opt-in skips, known AnyIO warning only. Native read-only
  PostgreSQL: 58 passed. Ruff lint/format passed (116 Python files); mypy passed
  22 implementation files. Final offline parse passed, retained artifacts:
  .artifacts/dbt/f4f3c81e90d946629fa980ca48771ad4. Scoped review corrected both
  issues; no remaining blocker. First/physical/repeat: Not yet tested; no product
  view or source mutation. Customer acceptance diff/staged/history scans passed; clean published
  dca21e9 confirmed before this unit.
- Customer: 81 focused tests; 819 warehouse/API regression passed /496 deliberately
  opted-out live tests; known AnyIO warning only. Native read-only SQL: 23 passed.
- Ruff lint/format passed (112 Python files); mypy passed 22 implementation files.
  Offline parse passed: .artifacts/dbt/2f4dc0c06e104e5a926ea96225c28621.
- Initial new test collection failed on a missing comprehension bracket; corrected,
  AST-parsed and all subsequent checks passed. No model/DB corruption occurred.
- First/repeat each passed one customer view/all four dbt tests; read-only actual-login
  physical/type/C-collation/full-source/private-access test: 1 passed. 99,441 source rows,
  96,096 identities, zero null identities, no omitted/extra/changed/duplicate members.
- Repeat identity/owner/grants preserved; password absent from both artifacts. Database
  287,190,163 bytes <400,000,000. Build suite times 22.417/21.895
  seconds include tests, not individual application-query latency. M5 performance pending.
- Complete staged-content/history secret scans passed before code a93cb7f publication.
  Customer acceptance diff/staged/history checks passed before clean publication.
- Historical accepted core: location first/repeat 12 dbt tests; seller 11 each; physical
  checks passed. See guides/JSON for dated offline/native/regression counts and artifacts.
- Source/frontend/dependency-advisory gate last passed 2026-09-22; not rerun for unchanged
  dependencies/data-only changes. Unmodified check.ps1 deletes generated resources and
  needs approval or reviewed retained workflow. E2E/deployment/full Phase 3 audit not run.

## Current Repository Condition

STABLE / SAFE TO RESUME. Product code/offline/native checks complete; live acceptance
pending. No known current failed tests or product view mutation. Published customer
acceptance dca21e9 is the pre-risk baseline; code checkpoint precedes first build.
Phase 3 remains incomplete.

## Incomplete Work

- M4: dim_product/dim_date, int_order_customers and four facts.
- M5: technical order-component mart, reliable examples, measured query plans/performance
  and reconstruction/recovery proof; aggregate independent children before joins.
- fact_order_items must retain shipping-before-purchase and >365-day warning flags
  (four historical >year rows); durations require valid ordered events.
- Multiple-review counts for 547 orders belong in core/mart; no selected-review policy.
- Recommended Phase2 parser debt: pandas accepts nonpadded dates/leap-second rollover/
  now/today. Strict warehouse guard mitigates; maintainer fixes before new source version.
- Recommended precise API double transport gate above, before coordinate reads.
  Carry forward documented E01-E10 audit revisit/release gates.
- Comprehensive governance audit/corrections only after verified Phase 3, before Phase 4.

## Exact Next Actions

1. Confirm published clean product code checkpoint and size <400,000,000 bytes;
   run selected dbt-build --select dim_product with protected transformer settings.
2. Run product physical/access check and compatible repeat build; all 32,951 source
   rows/IDs, 610 missing/13 untranslated categories and four zero weights retained.
   Confirm full fields/types, private denials, identity/grants, size and artifacts.
3. Record evidence/docs/acceptance checkpoint and detailed session report. Wrap this
   round with dim_date as the exact next unit; do not begin another model now.
4. Remaining core/M5/governance work retains existing phase boundaries.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Published pre-risk baseline: seller acceptance 1320900; customer code a93cb7f.
- Customer acceptance dca21e9 published; working tree was clean/synced before
  this product unit. Product code checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md; verify clean/synced publication.
- Latest observed allowance 63% five-hour/84% weekly remaining, account-wide; not a
  reservation. Session began after reset at 99%/89%. No paid changes/reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
# Optional accepted-unit check; never reload/restart completed phases.
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_customer
```

Use customer-staging.md's retained warehouse/API regression workflow and the customer
dimension guide. Never print secrets/source records/driver diagnostics. Resource deletion
needs specific informed permission; legitimate product deletion follows authorized
ownership/confirmation/integrity behavior. Preserve owner's retained C and new artifacts.
