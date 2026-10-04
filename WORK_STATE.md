# CommerceLens work state

Authoritative handoff; reconcile actual repository/Git/documentation before resuming.
Updated 2026-10-04. Master plan, ADR 0003, engineering standards, execution and deletion
protocols apply. Synced project references and source datasets remain unchanged.

## Project State

- Phase 3 Database/SQL/Analytics Engineering: M4 complete; next milestone M5.
- Customer identity COMPLETE, code/acceptance a93cb7f/dca21e9 published clean.
- Product unit COMPLETE, published acceptance 055ba10 clean/synchronized on resume.
- Date COMPLETE, published acceptance ca44c12 clean/synchronized before this unit.
  All five dimensions/mapping and core.fact_orders COMPLETE.
  Source/offline/native/first live/physical/repeat acceptance passed. Source
  b57a416 and bounded runner correction 8c170b6 published before live builds.
  Order-fact acceptance 7a3199e published; clean/synchronized on resume.
  Current unit: fact_order_items COMPLETE. Source/offline/native/first/
  physical/repeat acceptance passed. Source a047ecf published before build.
  Current atomic unit: fact_payments COMPLETE. Source e50d47c published;
  source/offline/native/first/physical/repeat acceptance passed.
  Current atomic unit: fact_reviews COMPLETE; source 23101c2 published
  before build. Source/offline/native/first/physical/repeat acceptance passed.
  M4 COMPLETE: nine staging views, five dimensions, customer mapping and
  four facts accepted. Larger Phase 3 SAFE TO RESUME; M5 not started.
- Objective: tested analytical warehouse under Free/views-first ADR 0004; M5
  remains. Phase 4 and comprehensive exit audit have not begun.
- Accepted product contract: all 20 staging fields unchanged plus nullable English
  translation/untranslated coverage (22 columns); no invented labels or dropped rows.
- Roughly 10-20% of Phase 3 warehouse implementation/verification effort remains;
  broad reasoned range, not model count/time forecast. Later audit effort is unknown.

## Completed Work

- Review fact/M4: all 99,224 pairs/twelve fields conserved, literal nullable
  comments/lineage/score/events/reversal warning and direct calendar roles.
  Missing titles/messages 87,656/58,247, reversals 0, multiple-review
  orders 547 retained. No selected review, duration or eligibility policy.
- Payment fact: all 103,886 composite components/ten fields conserved with
  exact source amount 16008872.12 and zero-installment/value/undefined
  warning counts 2/9/3. No joins/aggregation/imputation/eligibility.
- Item fact: all 112,650 item keys/15 fields conserved; exact source price
  13591643.70/freight 2251909.54, both lineages/context/direct shipping date
  and 0-before/4-beyond-365-day warnings retained. No eligibility policy.
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
- Order fact: all 99,441 orders/33 fields conserved with 96,096 identities,
  both lineages, five date roles, all lifecycle flags and 278 uncovered rows.
- Mapping: all 99,441 order-linked customer records/96,096 identities conserved
  across raw/stage/core, with seven unchanged fields and all 278 uncovered rows.
- Date: 755 observed dates across 803,395 events; all eight raw/staged clocks
  (808,303 positions including NULLs/lineage) conserved. All nine fields verified.
- Seller: all 3,095 IDs/rows and seven uncovered addresses/lineage retained.
- Product: 32,951 rows/IDs; all 20 fields/lineage retained, English enrichment verified,
  610 missing-category/13 untranslated/four zero-weight rows preserved.
- Customer: 96,096 literal identities; independent raw/stage/core membership matched.
  All 99,441 source/staging address/lineage records unchanged; no chosen current address.
- Approved cleanup A/B/D completed 177c71d; C dataset fallback/three drafts retained.
  New retained validation artifacts are not covered by that old deletion approval.

## Files

- Review fact: SQL/YAML, four singular checks and fact-reviews.md created;
  runner selector, three reviewed test modules and handoff/phase/customer
  guidance updated. Aggregate review evidence created; README/review/date/
  core guides updated. No reload/dependency/credential change or deletion.

- Payment fact: SQL/YAML, four singular checks and fact-payments.md created;
  runner selector added, handoff/phase/customer guides updated;
  three reviewed offline/native/physical test modules adopted. No accepted
  source/dependency change or resource deletion. Aggregate payment evidence
  created; README/staging/core/phase guides updated; outputs retained.

- Item fact: fact_order_items.sql/.yml, four singular tests and
  fact-order-items.md created; runner approved selector added. Candidate
  three offline/native/physical test modules adopted after AST validation.
  fact-order-items-verification.json created; README/staging/fact/phase guides
  updated. Artifacts .artifacts/dbt/0e137cd093ad41179fb41a17662131a3 and
  .artifacts/dbt/d1371f62447c4a62ac1c279074f56e7e. No deletion/rename; artifacts retained.
- Fact orders: fact_orders.sql/.yml, three singular SQL tests and fact-orders.md
  created; three fact-order Python test modules adopted. Runner/phase/staging
  guides/README updated; fact-orders-verification.json created. Artifacts:
  .artifacts/dbt/ef1e2c522e704d11857a907edcb9da56 and
  .artifacts/dbt/063713da68cf4298af22596a04a52285. Interrupted
  repeat 8b6d4807b6544cb89fa67dd409a029c0 also retained. No deletion/rename.
- Mapping: intermediate int_order_customers.sql/.yml, three singular tests, three
  Python test modules and order-customers.md created; runner/phase/staging guides
  updated. order-customers-verification.json added; README/identity guide updated.
  First/repeat artifacts: .artifacts/dbt/ad8d4822c4734c93a285790b0384126f
  and .artifacts/dbt/509157200a46424fba7b1b7ffa52e74a. No files deleted/renamed; artifacts retained.
- Created date SQL/YAML, date domain/reconciliation SQL tests, three date test modules
  and date-dimension.md; approved runner selector updated. All candidates/artifacts
  retained. date-dimension-verification.json added; README/phase/guide updated.
  First/repeat artifacts: .artifacts/dbt/a2c5c1281a214f3bbb670b77f73b2b83
  and .artifacts/dbt/3b3f887a9f01495b88acc9f14df5d223. No files deleted or renamed.
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

- Review fact retains ten accepted staging fields plus two direct calendar
  roles to dim_date at (review_id,order_id); neither ID alone is unique.
  Literal optional comments and event reversals survive unchanged. No joins,
  durations, selected review or eligibility. Membership is tested separately.
  Multiple-review counts remain independently aggregated M5 responsibility.
- Payment fact preserves all ten accepted staging fields at (order_id,
  payment_sequential), including exact money/lineage/three warnings.
  No joins or business policy; mandatory literal fact_orders membership
  is validated separately. Four singular and ten required-field checks.
- Active item fact: private view at (order_id, order_item_id), preserving nine
  staging item fields including exact money. One literal C LEFT JOIN to
  accepted fact_orders adds purchase context and separate order load/ordinal.
  Exact timestamp comparisons add shipping-before-purchase and strictly
  >365 elapsed-day warning flags; direct shipping date references dim_date.
  Fifteen fields/19 tests; independent source-item count and composite grain
  block shared parent fanout. Missing parent retains item/NULL context, then
  fails required/reference gates. No extra attribute joins/durations/KPIs.
- Reviewed runner budget: parse/debug keep 120 seconds; approved one-model
  build/test suites get 180 seconds. The first 33-test suite took 115.488
  seconds, leaving little cumulative runtime margin. SQL 60s/lock 10s/idle
  transaction 60s limits, one thread, zero retries, secrets/selection/full-result
  gates unchanged. Individual measured queries were below 20 seconds; consumer
  profiling remains M5. This is a bounded overall workload allowance.
- Active fact_orders: all 22 accepted order staging fields/flags unchanged,
  six order-linked customer identity/address/lineage fields, five calendar-date
  roles from unchanged timestamps. One literal C LEFT JOIN to mapping only.
  Separate required mapping/identity/ZIP/date membership tests; source count
  guard plus full-field multisets/grain block shared join fanout. Optional
  clocks retain NULL dates; uncovered geography remains valid. No durations,
  child joins, eligibility/monetary metrics or separate delivery fact now.
- Active int_order_customers: reusable private core view in intermediate directory,
  one source customer_id, exactly seven unchanged staging fields/types/collations.
  Repeated identity with different addresses/lineage remains valid. No join, filter,
  recast, deduplication, current address or extra coverage/metric is introduced.
  Literal identity/ZIP parent membership is required; false geolocation is valid.
- Active dim_date contract: distinct nonnull observed dates from all eight retained
  order/item/review timestamp columns, nine standard date/calendar/ISO/weekend fields.
  No generated gap calendar, timezone invention, warning/status/KPI eligibility filter.
  Optional missing events contribute no date; malformed source parsing still blocks
  accepted staging validation. Fact timestamps remain available independently.
- dim_customer is ONLY customer_unique_id text DISTINCT with C collation. Repeating
  order-linked identities collapse at the declared identity grain; null/invalid IDs
  stay visible and block tests. Source addresses/load/ordinal are not chosen arbitrarily;
  accepted int_order_customers preserves them for fact_orders. No surrogate/counter/KPI.
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

- Review fact: independent source/main harness/final handoff reviews approved.
  Candidate offline 59 passed (0.51s); adopted review/runner 143 passed
  (15.56s); warehouse/API 1283 passed/910 deliberate live skips (29.50s),
  known AnyIO alias warning only. Native read-only PostgreSQL 52 passed
  (61.55s), all twelve fields, literal comments, Python naive dates under
  two timezones/collations, pair grain/reversals/NULLs/membership/mutations.
  Nonhex baseline fixture ID corrected before execution, no model change.
  Ruff lint/format (140 reported files), mypy (22 implementation files),
  offline parse .artifacts/dbt/d71b5d9b05624b4c99e3946101205900 passed.
  Preflight passed; raw reversal was not measured there, independently
  verified in physical acceptance. Source 23101c2 published clean after
  complete 14-file staged/history scans. First/repeat each passed one
  view/all 14 tests in 65.287/68.7s. Physical/access 2 passed:
  independent guarded raw/staging/core full ten/twelve-field multisets,
  literal comments, both lineage fields/events/reversal/direct dates, expected
  native types/typmods/collations, source bounds, required order/date
  membership and restricted login/role/verify-full TLS/private API/reader
  denials. Counts/missingness/reversals/multiple-review orders conserved;
  repeat preserved view OID/owner/grants and password absent from artifacts.
  Database 287,288,467 bytes <400M. Paths/results in fact-reviews-verification.json.
  No known failed review gates remain; source/accepted models unchanged.
  M4 accepted individually across nineteen models; full source/frontend/
  advisory gate remains historical, no E2E/deployment/full exit audit run.
  Scoped final acceptance diff/handoff reviewed; complete eleven-file
  staged-content/history scans passed. Publish containing checkpoint
  and confirm clean/synchronized Git before handoff.


- Payment fact: independent candidate source and main harness/final handoff
  reviews approved. Candidate offline 55 passed (0.43s); adopted payment/
  runner 137 passed (15.64s); warehouse/API 1222 passed/856 deliberate live
  skips (27.04s), known AnyIO alias warning only. Native read-only 45
  passed (52.90s), complete ten-field preservation/mutations, exact cents/
  maximum numeric, split methods/warnings, NULLs/literal membership/domains/
  grain/empty fixtures. Ruff lint/format 136 reported files and mypy 22
  implementation files passed; offline parse retained
  .artifacts/dbt/6f7b26ba4fd14ffb9be2b953a7a37e57. Preflight passed with
  absent view/accepted parents and expected 103,886 keys/sum/flags.
  Complete 14-file staged-content/history scans passed before source
  e50d47c published clean. First/repeat each passed one view/all 14 tests
  in 55.391/57.386s. Physical 2 passed (24.69s): independent guarded
  raw/staging/core complete multisets/lineage/exact money/flags, native
  types/typmods/collations, restricted actual login/role/verify-full TLS/
  private API/reader denials. Repeat preserved counts/sum/flags/view OID/
  owner/grants; password absent from first/repeat artifacts. Database
  287,263,891 bytes <400M. Artifact paths/results in fact-payments-verification.json.
  No known failed payment checks remain; accepted models/raw unchanged.
  Suite runtime is not consumer latency; M5 plans/recovery remain pending.
  Scoped final acceptance diff/handoff reviewed; complete nine-file
  staged-content/history secret scans passed. Publish containing
  checkpoint and confirm clean/synchronized Git. No resource deletion.

- Item fact: scoped source/harness reviews approved. Candidate offline 79
  passed; adopted item/runner focused 159 passed (19.11s); regression 1165
  passed/809 deliberate live skips (28.50s), known AnyIO warning only.
  AST/import-group adoption, Ruff lint/format 132 reported files and mypy
  22 implementation files passed. Adopted native read-only PostgreSQL 69
  passed (96.97s), including exact numeric(18,2), all 15 fields, boundaries,
  shared parent fanout, required references/NULLs and empty typed fixtures.
  Offline parse passed: .artifacts/dbt/6179cb386aca49eca12b134cef5a6ed3.
  Read-only preflight confirmed view absent/parents present and expected
  row/key/money/chronology counts; database 287,247,507 bytes. Initial helper
  quoting error prevented execution; fixed before preflight, no DB mutation.
  Full 14-file staged-content/history scans passed; source a047ecf published
  clean before first live build. First/repeat each passed one view/all 19
  tests in 106.982/106.281 seconds. Physical/access 2 passed: independent
  raw/stage/core full 15-field multisets, exact money/both lineages/context/
  flags/date retained; inherited types/typmods/collations and restricted
  actual login/role/verify-full TLS/private API/reader denials verified.
  Repeat preserved relation identity/owner/grants and source counts/money/
  warnings; password absent from first/repeat artifacts. Database
  287,255,699 bytes <400,000,000. See fact-order-items-verification.json.
  No failed item checks remain; accepted models/source unchanged. Suite
  timings are not consumer latency; M5 measured plans/recovery remain.
  Final handoff/evidence consistency review and complete eight-file staged
  contents/history secret scans passed. Source/runner scans passed before
  a047ecf publication. Final containing acceptance commit must be published
  and Git confirmed clean/synchronized before closing and on resume.
  Acceptance-recorder section guard initially stopped before writes; fixed
  and recorded complete acceptance without source/DB changes.

- Fact orders: source/offline/native/physical reviews approved. Read-only
  preflight passed (view absent/parents present, 99,441 raw orders/IDs,
  database 287,222,931 bytes). Initial offline parse passed:
  .artifacts/dbt/8d56aa1f4d9e4a0892645244105d12c8. Offline candidate/adopted
  104 passed each; native read-only PostgreSQL 97 passed. Initial regression
  1075 passed/738 deliberate live skips, known AnyIO warning only. Initial
  adopted lint found two import-spacing issues; fixed, lint/format 128 files
  and mypy 22 source files passed. Source b57a416 published before first build.
  First: one view/all 33 tests passed in 115.488 seconds; artifacts:
  .artifacts/dbt/ef1e2c522e704d11857a907edcb9da56. Physical/access 2 passed:
  independent raw/stage/core 33-field multisets, both lineages/flags/NULL
  dates, inherited types/collation, actual restricted login/role/verify-full
  TLS and private API/reader denials verified. Interrupted repeat failed
  with DbtError and no complete run_results; exact suppressed reason unknown.
  Retained .artifacts/dbt/8b6d4807b6544cb89fa67dd409a029c0; view preserved.
  First suite left little margin in old overall 120-second budget; scoped
  120/180 setup/model-suite correction reviewed/validated/published 8c170b6.
  No data assertion/query timeout limit weakened. Initial runner fixture
  75 passed/3 debug mock failures (assumed target-path available) fixed via
  log-path; final runner 78 passed (17.98s), regression 1084 passed/738 live
  opt-out skips (36.00s), known AnyIO warning only. Ruff lint/format 128
  files, corrected fixture checks and mypy 22 source files passed. Revised
  offline parse passed: .artifacts/dbt/536178186f66417d93d5cbdec0686329.
  Repeat retry: one view/all 33 tests passed in 115.521 seconds;
  artifacts .artifacts/dbt/063713da68cf4298af22596a04a52285. All 99,441
  orders/96,096 identities/278 uncovered rows, original flags and optional
  NULL-date counts conserved. Relation identity/owner/grants unchanged;
  password absent from first/successful-repeat artifacts. Database 287,247,507
  bytes <400,000,000. No unresolved fact-order acceptance failures remain;
  failed attempt remains recorded. See fact-orders-verification.json.
  Suite timings include data tests and network, not consumer-query latency.
  M5 performance/reconstruction remains pending. Complete eight-file staged
  contents/history secret scans and scoped independent handoff review passed.
  Source/runner published after their scans. Repeat final scans after these
  wording updates; publish containing acceptance commit and confirm Git.
  No merge/deployment performed; live privacy/access evidence is scoped.

- Order-customer mapping: scoped contract review approved; 46 candidate offline
  tests passed. Adopted focused suite 113 passed; warehouse/API regression
  969 passed/639 deliberate live opt-out skips, known AnyIO warning only.
  Native read-only PostgreSQL 44 passed. Ruff lint/format passed (124 reported
  files); mypy passed 22 implementation files. Offline dbt parse passed:
  .artifacts/dbt/b874d3838e1c44f4b46090388bb16707. No failing mapping checks.
  First live build passed one view/all 12 dbt tests (48.398 seconds).
  Retained artifacts: .artifacts/dbt/ad8d4822c4734c93a285790b0384126f.
  Physical/access: 1 passed. Raw/stage/core full seven-field multisets,
  types/collation, restricted actual login/role/verify-full TLS and private
  API/reader denials verified; all 99,441 rows/96,096 identities/278 uncovered
  rows preserved. Repeat passed one view/all 12 dbt tests in 46.051
  seconds; relation identity/owner/grants and source/coverage counts preserved.
  Password absent from first/repeat artifacts. Database 287222931 bytes
  <400,000,000. Complete build-suite timings are not consumer-query latency.
  See order-customers-verification.json. Code 0badc24 passed complete staged
  contents/history secret scans and was published clean before build.
  No source reload or schema migration required; no mapping failures remain.
- First date build passed in 107.963 seconds, close to runner's 120-second bound.
  Domain node took 35.32 seconds. Reviewed semantics-preserving MATERIALIZED
  boundary added to the date consistency test so attributes are checked after
  deriving the small date domain. SQLite 3.50.4 confirmed; 35 focused and 38
  native read-only cases passed again. Final offline parse passed, retained:
  .artifacts/dbt/14923cd418ec495b9243c3e3f78323f9. Repeat suite passed in
  76.572 seconds, versus first 107.963 seconds.
  No test assertion removed; scoped boundary review approved. Consumer-query
  performance/recovery remains M5; these timings include data tests.
- Date: candidates AST-parsed; scoped independent review approved. 35 candidate
  offline cases passed after sandbox collection access was resolved with confined
  collection/escalation (initial attempt collected none; no code failure/mutation).
  Adopted focused suite: 100 passed; warehouse/API regression 921 passed/594 deliberate
  live skips, known AnyIO warning only. Native read-only PostgreSQL 38 passed,
  including two timezones and typed empty results. Ruff lint/format passed (120
  Python files); mypy passed 22 implementation files. Offline dbt parse passed:
  .artifacts/dbt/5cb60ba4980e40efa6e1ce907c7c6e8f. First build passed one view/all
  12 dbt tests (107.963 seconds), retained artifacts .artifacts/dbt/a2c5c1281a214f3bbb670b77f73b2b83.
  Physical/access: 1 passed. Repeat: one view/all 12 dbt tests passed.
  Actual restricted login/verify-full TLS, expected types/owner, all eight raw/staged
  event multisets and all nine dimension attributes matched; API/reader access denied.
  Repeat relation identity/owner/grants preserved; password absent from both artifacts.
  Database 287,222,931 bytes <400,000,000. Date code 9975935 and
  validation-boundary improvement eaac436 published before their respective builds.
  Preflight 803,395 nonnull events/755 dates (2016-09-04..2020-04-09), raw counts
  unchanged; no date view existed, database 287,222,931 bytes <400,000,000.
- Product code adopted after all three Python modules passed AST parsing;
  Initial focused124/lint116/mypy 22/regression882/parse passed; native57 passed/2
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

CLEAN / STABLE at published M4 acceptance checkpoint; verify Git on resume.
Payment/review units COMPLETE; M4 COMPLETE; larger Phase 3 SAFE TO RESUME.
M5 not started. No failed checks, partial next model, migration, source/
dependency/credential mutation or resource deletion. Governance/Phase 4 pending.

## Incomplete Work

- M4 complete: all nine staging models, five dimensions, mapping and
  all four facts accepted. Do not restart or redo them.
- M5: technical order-component mart, reliable examples, measured query plans/performance
  and reconstruction/recovery proof; aggregate independent children before joins.
- Shipping warnings are accepted in fact_order_items; later durations
  still require present ordered events. No business eligibility added.
- Review fact retains all pairs; M5 must independently aggregate review
  counts, preserving 547 multiple-review orders, without selected-review policy.
- Recommended Phase2 parser debt: pandas accepts nonpadded dates/leap-second rollover/
  now/today. Strict warehouse guard mitigates; maintainer fixes before new source version.
- Recommended precise API double transport gate above, before coordinate reads.
  Carry forward documented E01-E10 audit revisit/release gates.
- Comprehensive governance audit/corrections only after verified Phase 3, before Phase 4.

## Exact Next Actions

1. Check usage/Git/history against this M4 checkpoint. Read ADR 0003's
   mart_order_components contract, phase-3-plan.md M5 and accepted four fact
   SQL/YAML/guides; inspect existing role/recovery contracts. No M4 rebuild,
   source reload, role reprovision or old phase implementation is needed.
2. Scope M5 at one order: independently aggregate each child before LEFT
   JOIN to fact_orders. Preserve all 99,441 orders; expose counts, exact
   source price/freight/payment amounts and quality/presence indicators.
   Zero child count must differ from real zero amounts; absent sums remain
   NULL. Retain multiple-review counts; no KPI/selected-review eligibility.
3. Implement/verify bounded mart unit with fanout/missing-child/money/quality
   fixtures, source conservation, private reader access and first/repeat
   acceptance; checkpoint. Recheck capacity before any materialization.
4. Reliable technical query examples and measured plans/performance; prove
   reconstruction/recovery using retained source and versioned migrations/
   dbt. Review any destructive resource actions before requesting permission.
5. Complete Phase 3 verification/docs/checkpoint, then comprehensive governance
   audit and required corrections before Phase 4; carry deferred debt forward.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Payment source
  e50d47c and review source 23101c2 published clean before their live builds.
  Payment acceptance 2829ce2 published after verified builds. M4/review
  acceptance checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Confirm clean/synchronized Git
  after publication and on resume. No merge/deployment.
- Latest observed allowance 64% five-hour/94% weekly remaining on
  2026-10-04, account-wide and not a reservation. No paid/reset credits used.
  Both fact units finished; M5 deliberately not started this session.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
# Optional accepted-unit check; never reload/restart completed phases.
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_customer
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_product
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_date
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select int_order_customers
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_orders
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_order_items
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_payments
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_reviews
```

Use customer-staging.md's retained warehouse/API regression workflow and the customer
and product/date dimension plus order-customers/fact-orders guides. Never print secrets/
source records/driver diagnostics.
Resource deletion needs specific informed permission; legitimate product deletion follows authorized
ownership/confirmation/integrity behavior. Preserve owner's retained C and new artifacts.
