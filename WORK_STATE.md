# CommerceLens work state

Authoritative handoff; reconcile actual repository/Git/documentation before resuming.
Updated 2026-10-04. Master plan, ADR 0003, engineering standards, execution and deletion
protocols apply. Synced project references and source datasets remain unchanged.

## Project State

- Phase 3 Database/SQL/Analytics Engineering, M4. All nine source staging views accepted.
- Customer identity COMPLETE, code/acceptance a93cb7f/dca21e9 published clean.
- Product unit COMPLETE, published acceptance 055ba10 clean/synchronized on resume.
- Current unit: core.dim_date code/offline/native COMPLETE; first/physical/repeat
  acceptance PENDING. No date view built yet; source remains unchanged.
- Objective: tested analytical warehouse under Free/views-first ADR 0004; M4 and M5
  remain. Phase 4 and comprehensive exit audit have not begun.
- Accepted product contract: all 20 staging fields unchanged plus nullable English
  translation/untranslated coverage (22 columns); no invented labels or dropped rows.
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
- Product: 32,951 rows/IDs; all 20 fields/lineage retained, English enrichment verified,
  610 missing-category/13 untranslated/four zero-weight rows preserved.
- Customer: 96,096 literal identities; independent raw/stage/core membership matched.
  All 99,441 source/staging address/lineage records unchanged; no chosen current address.
- Approved cleanup A/B/D completed 177c71d; C dataset fallback/three drafts retained.
  New retained validation artifacts are not covered by that old deletion approval.

## Files

- Created date SQL/YAML, date domain/reconciliation SQL tests, three date test modules
  and date-dimension.md; approved runner selector updated. All candidates/artifacts
  retained. No files deleted or renamed.
- New product unit: dim_product.sql/.yml, product_dimension_domains/source
  reconciliation tests, three product-dimension Python test modules and guide.
  product-dimension-verification.json added; runner selector, README, work state
  and phase/customer/product staging guides updated; no deletion.
  Product first/repeat artifacts: .artifacts/dbt/2963bc06961a4a3da65e7d25b10d3c51
  and .artifacts/dbt/7064f7fbbf0d47c0b7a5987a3499f624.
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

- Active dim_date contract: distinct nonnull observed dates from all eight retained
  order/item/review timestamp columns, nine standard date/calendar/ISO/weekend fields.
  No generated gap calendar, timezone invention, warning/status/KPI eligibility filter.
  Optional missing events contribute no date; malformed source parsing still blocks
  accepted staging validation. Fact timestamps remain available independently.
- dim_customer is ONLY customer_unique_id text DISTINCT with C collation. Repeating
  order-linked identities collapse at the declared identity grain; null/invalid IDs
  stay visible and block tests. Source addresses/load/ordinal are not chosen arbitrarily;
  later int_order_customers preserves them for fact_orders. No surrogate/counter/KPI.
- Four dbt tests: not-null, unique, ASCII lowercase32hex domain and full bidirectional
  EXCEPT ALL identity membership. Source/dimension duplicate semantics differ deliberately.
- Accepted dim_product: retain all staging fields/flags, literal category left join; nullable
  English plus is_untranslated_category distinguishes 610 missing/13 untranslated rows.
  Matched lookup with null English or duplicate keys blocks; no dedup/filter/fill labels.
  Independent source/output cardinality supplements full EXCEPT ALL: a shared bad
  lookup can fan out both expected/actual joins. Missing-category flag must agree
  with nullable source category; English spelling is verified by reconciliation.
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

- Date: candidates AST-parsed; scoped independent review approved. 35 candidate
  offline cases passed after sandbox collection access was resolved with confined
  collection/escalation (initial attempt collected none; no code failure/mutation).
  Adopted focused suite: 100 passed; warehouse/API regression 921 passed/594 deliberate
  live skips, known AnyIO warning only. Native read-only PostgreSQL 38 passed,
  including two timezones and typed empty results. Ruff lint/format passed (120
  Python files); mypy passed 22 implementation files. Offline dbt parse passed:
  .artifacts/dbt/5cb60ba4980e40efa6e1ce907c7c6e8f. First/physical/repeat: Not yet tested.
  Preflight 803,395 nonnull events/755 dates (2016-09-04..2020-04-09), raw counts
  unchanged; no date view existed, database 287,222,931 bytes <400,000,000.
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
  issues; no remaining blocker. First/repeat each passed one view/all 16 dbt tests;
  physical/access: 1 passed. All 32,951 source/stage/dimension rows/IDs, 610 missing
  categories/13 untranslated/four zero-weight rows retained; zero null coverage.
  Full staged fields/types and independent raw key/English/coverage comparisons
  passed. Actual login/verify-full TLS, ownership and API/reader denials verified.
  Repeat identity/owner/grants preserved; password absent from both artifacts.
  Database 287,214,739 bytes <400,000,000. Complete suite times
  49.741/50.017 seconds include tests, not application-query latency.
  M5 performance/recovery remains pending; see product-dimension-verification.json.
  Product complete staged-contents/history scans passed before code 5d96701.
  Acceptance diff/full-staged-content and pre-commit history scans passed; independent
  handoff review approved. Repeat history scan before publication and confirm Git.
  Customer acceptance diff/staged/history scans passed; clean published dca21e9
  confirmed before this unit.
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

STABLE / SAFE TO RESUME. Date code/offline/native checks passed; first/physical/
repeat acceptance pending. No known failed tests, migration or source mutation.
Verified product baseline 055ba10 preserved; date code checkpoint precedes first
live build. Phase 3 remains incomplete.

## Incomplete Work

- M4: dim_date, int_order_customers and four facts. Four of five dimensions accepted.
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

1. Confirm clean/published date code checkpoint and budget <400,000,000 bytes;
   run selected dbt-build --select dim_date through the protected transformer wrapper.
2. Run date physical/access check, covering all eight raw/staged clocks with lineage
   including NULL positions, exact date/calendar membership, types and private denials.
3. Run compatible repeat build; verify identity/owner/grants/source counts/storage
   and no password in first/repeat artifacts. Save aggregate evidence and acceptance.
4. Continue int_order_customers/four facts/M5 as allowance permits; keep phase boundaries
   and the required governance gate after verified Phase 3, before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Published pre-risk baseline: seller acceptance 1320900; customer code a93cb7f.
- Customer acceptance dca21e9 published; working tree was clean/synced before
  this product unit. Product code/acceptance 5d96701/055ba10 published. Date code
  checkpoint is the containing commit: git log -1 --format="%H %s" -- WORK_STATE.md;
  verify clean/synced publication. No merge/deployment performed.
- Latest observed allowance 82% five-hour/80% weekly remaining on 2026-10-04,
  account-wide and not a reservation. Prior session ended at a recoverable checkpoint.
  No paid changes/reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
# Optional accepted-unit check; never reload/restart completed phases.
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_customer
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_product
```

Use customer-staging.md's retained warehouse/API regression workflow and the customer
and product dimension guides. Never print secrets/source records/driver diagnostics.
Resource deletion needs specific informed permission; legitimate product deletion follows authorized
ownership/confirmation/integrity behavior. Preserve owner's retained C and new artifacts.
