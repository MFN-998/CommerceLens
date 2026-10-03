# CommerceLens work state

Authoritative handoff; verify actual repository, Git and documentation on resume.
Updated 2026-10-03. Required continuation knowledge must not depend on chat alone.

## Project State

- Phase 3 Database/SQL/Analytics Engineering, M4. ALL NINE SOURCE STAGING MODELS COMPLETE.
- Current milestone: geolocation code/native/first/access/repeat acceptance COMPLETE.
  Next implementation unit: core.dim_location. No partially implemented core files.
- Objective: tested analytical warehouse per master plan, ADR 0003 and Free/views-first
  ADR 0004. M4 core and M5 remain; Phase 4 and the comprehensive exit audit have not begun.
- Roughly 35-45% of Phase 3 warehouse implementation/verification effort remains after
  source staging. Reasoned range, not a time forecast or model-count percentage;
  required later audit/correction effort remains unknown.

## Completed Work

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

- New dbt/models/staging/stg_geolocation.sql/.yml; three singular tests
  stg_geolocation_lineage_unique/source_domains/source_reconciliation.sql.
- New tests/test_warehouse_geolocation_staging.py, native _postgres_integration.py,
  physical _integration.py; docs/geolocation-staging.md and verification JSON.
- Modified approved selector in src/warehouse/dbt_runner.py; no helper changes.
- Updated README, CONTRIBUTING, development/dbt-setup/phase-3/customer-staging docs
  and cleanup follow-up record. No dependency, migration, raw/interim data, credentials,
  application, filesystem deletion or deployment changes in this geolocation unit.
- Retained first/repeat artifacts: .artifacts/dbt/033ad85c890342d683eb9debfe704158
  and .artifacts/dbt/bfcb642cd6fa413282978a3d61fc5b87.

## Technical Decisions

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
- Core.dim_location next: literal ZIP union of customers/sellers/geolocation; aggregate
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

STABLE / SAFE TO RESUME. Geolocation atomic unit COMPLETE; all nine source staging
views accepted. Phase 3 is still incomplete. No current known failed tests.
Acceptance documentation is saved; verify containing checkpoint and actual Git status.

## Incomplete Work

- Core.dim_location, then remaining four dimensions, int_order_customers and four facts.
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

1. Read phase-3-plan.md, ADR 0003 dim_location contract and accepted staging models.
   Confirm clean/synced checkpoint. Implement core.dim_location with the minimal
   observation/coverage/ambiguity contract above and dedicated selector/tests/guide.
2. Verify unique exact three-source ZIP domain, duplicate-preserving per-ZIP counts,
   nonnegative bounded counters, source totals and boolean consistency. Synthetic
   duplicates increase observation counts without changing literal variant counts.
   Unique-domain joins preserve customer/seller rows and 278/7 uncovered source rows.
3. Validate offline/native gates, checkpoint code, selected first/physical/repeat builds,
   record evidence/identity/access/storage and checkpoint. No raw reload or view drop.
4. Continue remaining M4 core units, then M5. Run full governance gate at phase exit.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Review acceptance 484249b.
- Cleanup 177c71d and geolocation implementation 81f0342 published.
- Geolocation acceptance checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md. Verify clean/synced status after publication.
- Last observed allowance 75% five-hour / 96% weekly remaining, account-wide;
  not a reservation for this task/model. Check before new substantial units.
  No purchases, paid changes or reset credits used.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_geolocation
```

Use customer-staging.md retained regression instructions and geolocation-staging.md.
Never print secrets/source records/driver diagnostics. Project resource deletion needs
specific informed permission; legitimate product deletion follows authorization,
ownership, confirmation and integrity requirements. Preserve the owner's retained C.
