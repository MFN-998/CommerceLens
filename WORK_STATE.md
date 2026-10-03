# CommerceLens work state

Authoritative handoff; verify actual repository, Git and documentation on resume.
Updated 2026-10-03. Required continuation knowledge must not depend on chat alone.

## Project State

- Phase 3 Database/SQL/Analytics Engineering, M4. ALL NINE SOURCE STAGING MODELS COMPLETE.
- Geolocation acceptance COMPLETE and published b2f4205.
- Location acceptance COMPLETE, clean published 7bd2d8c.
- Current unit: core.dim_seller COMPLETE; first/physical/repeat acceptance passed.
  This session is wrapped at a recoverable checkpoint per the owner's usage request.
  Resume core.dim_customer after the five-hour reset; do not restart earlier units.
- Objective: tested analytical warehouse per master plan, ADR 0003 and Free/views-first
  ADR 0004. M4 core and M5 remain; Phase 4 and the comprehensive exit audit have not begun.
- Roughly 30-40% of Phase 3 warehouse implementation/verification effort remains after
  source staging and accepted location/seller dimensions. Reasoned range, not a time forecast
  or model-count percentage;
  required later audit/correction effort remains unknown.

## Completed Work

- Seller dimension accepted: all 3,095 source sellers/unique IDs and unchanged
  lineage/address fields; seven uncovered rows retained, zero null coverage rows.
  Private access/type checks and compatible repeat identity/owner/grants passed.
- Location dimension accepted: 19,177 unique ZIPs; all 1,000,163 observations / 31
  broad-box flags; 8,556 city-ambiguous / 8 state-ambiguous ZIPs. Customer/seller joins
  retain 99,441/3,095 rows and 278/7 uncovered source rows.
- Phases 1-2 and professional-practices remediation complete; do not repeat them.
- M1 contracts, M2 isolated foundation, M3 all-nine-table landing complete:
  1,550,922 rows. No reload, migration replay or account reprovisioning needed.
- Accepted staging rows / historical dbt test counts: customers 99,441 / 12,
  sellers 3,095 / 11, category translation 71 / 8, products 32,951 / 16,
  orders 99,441 / 25, items 112,650 / 16, payments 103,886 / 16,
  reviews 99,224 / 14, geolocation 1,000,163 / 12. Later child relationships can
  expand parent test selections through eager indirect selection.
- Geolocation preserves 19,015 ZIPs, 261,831 excess exact duplicate observations,
  all 31 broad-Brazil-box outliers and immutable load/ordinal lineage.
- Approved 2026-10-02 cleanup A/B/D completed and verified; C dataset fallback and
  three unique drafts retained. Current 2026-10-03 test outputs are new retained
  artifacts, not additional deletion covered by that previous approval.
- Known progress/setup/test-location documentation wording corrected, without
  removing historical plans/evidence. Staged secret scans avoid duplicate exports.

## Files

- Current new seller unit: dbt/models/core/dim_seller.sql/.yml, seller_dimension_domains/
  source_reconciliation singular tests, tests/test_warehouse_seller_dimension.py and
  docs/seller-dimension.md; dedicated _postgres_integration.py and _integration.py
  seller-dimension tests added. Runner selector/phase/customer guides updated;
  docs/seller-dimension-verification.json, WORK_STATE and README updated;
  no deletion/migration/dependency/application/credential work.
- New dbt/models/core/dim_location.sql/.yml; domains/source_reconciliation/
  join_conservation singular tests; three dedicated location Python test modules
  and docs/location-dimension.md plus aggregate verification JSON. Modified runner
  approved selector and phase/
  customer-staging guides. No deletion/dependency/migration/application changes.
- New dbt/models/staging/stg_geolocation.sql/.yml; three singular tests
  stg_geolocation_lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_geolocation_staging.py, native _postgres_integration.py,
  physical _integration.py; docs/geolocation-staging.md and verification JSON.
- Modified approved selector in src/warehouse/dbt_runner.py; no helper changes.
- Updated README, CONTRIBUTING, development/dbt-setup/phase-3/customer-staging docs
  and cleanup follow-up record. No dependency, migration, raw/interim data, credentials,
  application, filesystem deletion or deployment changes in this geolocation unit.
- Retained seller first/repeat artifacts: .artifacts/dbt/4d97d80c8e4b437fb20143f554b0aee2
  and .artifacts/dbt/a51125dca35e431cb24656113bf5d90c.
- Retained location first/repeat artifacts: .artifacts/dbt/79e391f8fb2543df9d9822fa18e6c0c6
  and .artifacts/dbt/232e607e452449ada592e5001bd0bd55.
- Retained geolocation first/repeat artifacts: .artifacts/dbt/033ad85c890342d683eb9debfe704158
  and .artifacts/dbt/bfcb642cd6fa413282978a3d61fc5b87.

## Technical Decisions

- Seller grain remains source seller_id. Preserve all six fields and lineage;
  a unique location ZIP join adds has_geolocation. Missing reference yields null and
  blocks acceptance, not a false coverage warning. Independent source reconciliation
  uses a unique observation ZIP set; no source filtering/canonical geography/policy.
- Seller ZIP relationship expands eager parent selection. Build seller first before
  repeating parent location tests that now refer to it. Historical counts remain dated.
- Geolocation grain is (_load_id,_source_row), not ZIP or five-field distinct value.
  All exact duplicate observations and spelling variants remain; no source joins,
  deduplication, padding, normalization or canonical coordinate/city/state policy.
- ZIP follows existing one-to-five ASCII digits, city/state remain literal text;
  exact-empty text becomes NULL. Mandatory missing/invalid values fail acceptance.
- Coordinates reuse guarded nullable_double, global lat[-90,90]/lng[-180,180] domains.
  NaN/Infinity extensions, invalid/overflow/underflow input becomes NULL, blocking
  validation. No explicit rounding or repair; double is the accepted binary64 type.
- is_outside_broad_brazil_bounds is the exploratory inclusive lat[-34,6]/lng[-74,-28]
  warning; false if either typed coordinate absent. It never determines eligibility.
- Current dev session extra_float_digits=0 rounds text results to 15 significant
  digits. Binary fetch/float8send proved stored coordinate correctness; native
  projections use binary=True with strict independent equality, not relaxed tolerances.
  No global/server/helper change. Later precise API coordinate reads need binary
  transport or a reviewed positive session output setting.
- Accepted core.dim_location: literal ZIP union of customers/sellers/geolocation; aggregate
  geography before joining that unique domain. Minimal counters: observation_count,
  city_variant_count, state_variant_count and outside_broad_brazil_observation_count
  (geolocation_ prefix for the first three); booleans has_geolocation and
  is_geolocation_city_ambiguous/is_geolocation_state_ambiguous. Counts/ambiguity describe
  geo observations only; later customer/seller models retain source geography separately.
  Missing geo evidence yields zero counters; no chosen coordinate/city/state. See ADR 0003.
- Restricted transformer, verify-full TLS, private schemas/API denials remain enforced.
  Compatible CREATE OR REPLACE preserves view identity/owner/grants. View commit precedes
  tests; failed acceptance is not rollback. Preserve failed view/artifacts and diagnose.

## Validation

- Seller pre-build: 87 focused offline/runner checks passed; retained warehouse/API
  regression 797 passed / 472 deliberate live opt-in skips, known AnyIO warning only.
  Native read-only synthetic PostgreSQL: 30 passed. Ruff lint/format passed (108 Python
  files); mypy passed 22 implementation files. Offline parse passed, retained
  .artifacts/dbt/c6b2cc865d514c9cb796219ea2b57ed8. Scoped review found no blockers.
- Seller first selected build passed one view and all 11 dbt tests; suite elapsed
  61.648 seconds. Artifacts: .artifacts/dbt/4d97d80c8e4b437fb20143f554b0aee2.
  Actual-login read-only physical/type/ownership/access check: 1 passed.
  Repeat passed one view/all 11 dbt tests; suite elapsed 51.264 seconds.
  All 3,095 rows/IDs and seven uncovered rows retained; no null coverage.
  Repeat identity/owner/grants preserved; password absent from both artifacts.
  Database 287,181,971 bytes <400,000,000. Suite times include tests, not individual
  application-query latency. M5 performance/recovery gates remain pending.
  Evidence: docs/seller-dimension-verification.json. Complete staged-contents/
  history secret scans passed before publishing seller code 9263bf2.
  Acceptance diff check and complete staged-contents/history secret scans passed.
  Verify the containing acceptance commit and clean/synced status on resume.
- Location: 121 focused offline/runner checks passed; retained warehouse/API regression
  767 passed / 441 deliberate opt-in skips, known AnyIO warning only. Native read-only
  synthetic PostgreSQL cases: 59 passed. Ruff lint/format passed (104 Python files),
  mypy passed 22 implementation files. Initial lint rejected two long test SQL strings;
  split without changing SQL and reran successfully. Final offline parse passed: .artifacts/dbt/2edcc933d6c64246b31b3e64bff16f87.
- Focused review added null consumed geo city/state/flag guard: aggregates ignore nulls;
  mixed valid/null inputs now fail domains. Literal C collation and unique-domain
  joins preserve spelling and avoid per-address observation scans. No broad audit run.
- Initial scratch preflight stopped before build with InsufficientPrivilege because
  it had not SET LOCAL ROLE for core metadata lookup. Corrected helper; grants/code
  unchanged. Subsequent first/repeat each passed one location view/all 12 dbt tests.
  Actual-login read-only physical/access check: 1 passed; all API roles and mart reader
  denied core access. 19,177 unique ZIPs; all 1,000,163 observations / 31
  broad-box flags; 8,556 city-ambiguous / 8 state-ambiguous ZIPs. Customer/seller joins
  retain 99,441/3,095 rows and 278/7 uncovered source rows.
- Location repeat identity/owner/grants preserved; password absent from both artifacts.
  Database 287,173,779 bytes <400,000,000. Build suite elapsed times
  78.768/75.849 seconds;
  these include 12 tests and are not individual application query latency. M5 query-plan
  and performance acceptance remains pending. Evidence: location-dimension-verification.json.
- Location implementation complete staged-contents/history secret scans passed before
  publishing 1ad6281. Acceptance diff and complete staged-contents/history scans passed.
- 2026-10-03: focused offline geolocation/runner 134 passed. Ruff lint/format passed
  (100 Python files); mypy passed 22 implementation files. Warehouse/API regression
  701 passed / 381 deliberate opt-in skips, known AnyIO deprecation warning only.
- Offline dbt parse passed: .artifacts/dbt/8cd0a32fc01c4bebba797a8b9cc3a7ed.
- Initial native run 71 passed / 1 high-precision text-transport assertion failed;
  diagnosed and corrected test transport. Subsequent complete native run: 72 passed.
- First/repeat each passed one geolocation view / all 12 dbt tests. Actual-login
  read-only physical/type/ownership/access acceptance: 1 passed. Both raw/view retain
  1,000,163 rows / 19,015 ZIPs / 261,831 excess duplicate observations / 31 warning flags.
  Repeat OID/owner/grants preserved; password absent from first/repeat artifacts.
  Database 287,165,587 bytes <400,000,000; evidence geolocation-staging-verification.json.
- Implementation complete staged-contents/history secret scans passed before publishing
  81f0342. Acceptance diff and complete staged-contents/history secret scans passed.
- Cleanup source/data/credentials/evidence/draft integrity checks passed 2026-10-02;
  details in cleanup-review-2026-10-02.md. No further deletion authorized by that batch.
- Full source/frontend/dependency-advisory gate last passed 2026-09-22; not rerun for
  unchanged dependencies/data-only work. check.ps1 automatic cleanup needs approval
  or a reviewed retained workflow. No E2E/deployment/comprehensive Phase 3 audit run.

## Current Repository Condition

CLEAN / STABLE at the published acceptance checkpoint; verify Git on resume.
Seller unit COMPLETE; larger Phase 3 SAFE TO RESUME. Source/location baseline
unchanged, no known current failed tests. Code checkpoint 9263bf2 preceded the
first seller view build; no raw reload, migration or resource deletion occurred.
The next unit is intentionally deferred until reset, not blocked by a failure.

## Incomplete Work

- Remaining dimensions dim_customer/dim_product/dim_date; int_order_customers
  and four facts. Next: dim_customer, one customer_unique_id per ADR 0003;
  cross-order identity only, with no arbitrary current-address selection.
- M5 technical order-component mart, reliable example SQL, measured query-plan/performance
  and reconstruction/recovery proofs. Independent child aggregation/conservation gates.
- Items shipping-before-purchase/over-365-day flags are a fact_order_items M4 gate,
  including four historical over-one-year rows; durations require valid ordered events.
- Multiple-review counts (547 orders) belong to core/mart; no selected-review policy.
- Recommended Phase 2 parser compatibility debt: pandas accepts nonpadded dates,
  leap-second rollover and dynamic now/today. Strict warehouse guard mitigates current
  source. Owner: maintainer; fix before accepting a different source version.
- Recommended future API coordinate result-transport gate above; implement before
  exposing precise coordinate reads. Audit E01-E10 revisit gates remain documented.
- Full governance audit and required corrections only AFTER verified Phase 3, BEFORE Phase 4.

## Exact Next Actions

1. After the five-hour reset, read this file and ADR 0003's dim_customer grain;
   confirm Git status/history against the containing seller acceptance checkpoint.
   Inspect staging.stg_customers SQL/tests and accepted location/seller evidence;
   resolve any discrepancy before changing code. Check actual usage first.
2. Implement only core.dim_customer cross-order identity at customer_unique_id
   grain. Preserve all identities; no chosen current address. Add focused source/
   grain/failure checks and approved selector, then code checkpoint before live build.
3. Verify offline/native, first/physical/repeat acceptance, document and checkpoint.
   Continue later units only as allowance permits; do not redo accepted staging.
4. Remaining core/M5/governance work stays within established phase boundaries.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Review acceptance 484249b.
- Cleanup 177c71d and geolocation implementation 81f0342 published.
- Geolocation acceptance b2f4205 and location code 1ad6281 published.
- Location acceptance 7bd2d8c and seller code 9263bf2 published. Seller acceptance
  checkpoint is the containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
  Verify clean/synced status after publication; main remains unchanged.
- Last observed allowance 32% five-hour / 89% weekly remaining, account-wide;
  not a reservation for this task/model. Check before new substantial units.
  No purchases, paid changes or reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
# Optional accepted-unit validation; do not rebuild/reload completed phases.
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_seller
```

Use customer-staging.md retained regression instructions, seller-dimension.md and
ADR 0003. Read staging.stg_customers and its tests before the next implementation.
Never print secrets/source records/driver diagnostics. Project resource deletion needs
specific informed permission; legitimate product deletion follows authorization,
ownership, confirmation and integrity requirements. Preserve the owner's retained C.
