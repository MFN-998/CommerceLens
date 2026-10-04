# CommerceLens work state

Authoritative handoff. Updated 2026-10-04. Read actual Git/files before resuming.
Master plan, engineering standards, execution protocol, deletion rule and ADRs apply.

## Project State

- Phase 3 Database/SQL/Analytics Engineering: M1-M4 COMPLETE; M5 in progress.
- Current milestone: initial order mart and analytical warehouse handoff.
- Current task: mart_order_components COMPUTATION VERIFIED. Source/offline/native/
  first/physical/repeat acceptance complete. Larger M5/Phase 3 SAFE TO RESUME.
  Scoped reader SELECT/effective access, examples, performance and recovery remain.
- Objective: tested warehouse under Free/views-first ADR 0004, preserving all source
  rows/quality warnings. No Phase 4 EDA, Phase 5 KPI policy or public deployment yet.
- Larger Phase 3 remains incomplete. Roughly 10-20% implementation/verification
  effort remained at M4 acceptance; this broad range is not a time forecast or
  model-count calculation. Exit governance-audit effort is still unknown.

## Completed Work

- Phases 1-2 and their professional-practices retrospective/remediation COMPLETE.
  See docs/phase-1-status.md, phase-2-status.md and engineering-audit-phase-1-2.md.
- M1 warehouse contract and M2 private development foundation COMPLETE; migration
  replay, capabilities/TLS/denials and disposable recovery checks passed 2026-09-21.
- M3 COMPLETE: nine immutable source tables, 1,550,922 rows, exact text/lineage,
  content/hash/money reconciliation and idempotent repeat. No reload needed.
- M4 COMPLETE, published checkpoint 1b67dc5. Nine staging views, five dimensions,
  int_order_customers and four core facts accepted first/physical/repeat.
- Key accepted evidence (full fields/types/results in corresponding docs/ JSON):

| Accepted model | Retained evidence |
| --- | --- |
| dim_location | 19,177 ZIPs; 19,015 covered; all 1,000,163 observations; 31 broad-box warnings; 8,556 city/8 state ambiguities |
| dim_seller | 3,095 sellers; seven uncovered addresses retained |
| dim_customer / int_order_customers | 96,096 identities / 99,441 seven-field purchase-associated customer records; 278 uncovered retained |
| dim_product | 32,951 rows/22 fields; 610 missing categories, 13 untranslated, four zero weights |
| dim_date | 755 dates; 803,395 events across eight clocks/808,303 positions including NULLs |
| fact_orders | 99,441 orders/33 fields; both lineages, five date roles, all lifecycle flags |
| fact_order_items | 112,650 rows/15 fields; price 13591643.70, freight 2251909.54; warning counts 0/4 |
| fact_payments | 103,886 components/10 fields; exact 16008872.12; warnings 2/9/3 |
| fact_reviews | 99,224 pairs/12 fields; missing title/message 87,656/58,247; reversal 0; 547 multiple-review orders |

- M5 accepted mart computation: one-order mart, 33 unchanged parent fields plus 16 independently
  aggregated component/count/presence/warning fields. Four singular checks and one
  configured not-null test; three reviewed offline/native/physical Python modules.
- Scoped source and harness reviews approved. Reader foundation-grant assumption in
  physical test corrected before execution (marts USAGE already granted, SELECT denied).
- Prior approved cleanup A/B/D completed 177c71d. Owner retained C dataset fallback/
  three drafts. Existing/new generated artifacts retained, not covered by old approval.

## Files

- Created dbt/models/marts/mart_order_components.sql/.yml; four
  dbt/tests/order_components_* checks; docs/order-components.md;
  tests/test_warehouse_order_components.py, *_postgres_integration.py,
  *_integration.py. Modified src/warehouse/dbt_runner.py, phase-3-plan.md,
  WORK_STATE.md. No project resource deleted or renamed.
- Created docs/order-components-verification.json; README/guide/phase plan updated.
- No accepted upstream model, migration, dataset, dependency, credentials, API/UI,
  materialization policy or deployment changes. Scratch candidates and .artifacts
  outputs are retained. Historical detail remains in docs/Git, not solely chat.

## Technical Decisions

- Independently aggregate each child before literal C LEFT JOINs to orders. All orders
  and order fields retained; no canonical review/status/business eligibility filter.
- Absent children: zero counts, false presence, NULL amount sums. Real zero distinct.
  Exact SUM(numeric) has unconstrained aggregate headroom; no numeric(18,2) recast,
  float, rounding, imputation or asserted item/freight/payment equality.
- Long-form union/group test compares each order/component independently, detecting
  redistributed counts/amounts even when global totals are unchanged. Parent full
  multiset/grain/domain gates complement it; upstream source gates remain intact.
- Private schemas outside Data API; restricted transformer and verify-full TLS.
  Reader has marts USAGE only; explicit approved-mart SELECT and effective positive/
  negative verification remain a separate M5 access step. No reader credential added.
- Compatible CREATE OR REPLACE retains relation identity/owner/grants and commits
  before tests. Failed acceptance is not rollback: preserve artifacts/view, diagnose;
  no full refresh/DROP/source reload or unapproved project deletion.
- Views-first/Free ADR 0004: database ceiling 400M, raw ceiling 367M; remeasure
  storage, overlap and consumer plans before any materialization. DB size is not
  proof of unlimited WAL/temp space. One source snapshot per target.
- Runner parse/debug 120s; one-model build/test 180s; SQL 60s/lock 10s/idle 60s,
  one thread, zero retries, safe error/no sensitive row logging. Physical harness 55s.

## Validation

- Current mart candidate offline: 85 passed. Adopted mart/runner: 171 passed.
- Retained warehouse/API regression: 1370 passed, 983 deliberately
  opted-out live checks. Known AnyIO alias warning only; no failing offline gates.
- Native read-only PostgreSQL: 71 passed. Actual model/singulars/installed
  null macro, independent Decimal oracle, 49 fields/native types/C literal keys,
  2x3x2 fanout, absence/real zero, exact cents, multiple maximum component sums,
  empty input, wrong/NULL/nonfinite/presence outputs and redistributed totals.
- Ruff lint/format (144 files) and mypy 22 implementation files passed.
  Initial native-test import spacing corrected; final lint passed. Offline dbt parse
  passed, retained .artifacts/dbt/f69941d5631743bc93b5fc6c3f6dbdb8.
- Preflight passed: four facts present and accepted counts/exact sums/warnings
  unchanged; mart absent; database 287,288,467 bytes below the 400 MB ceiling.
- First/repeat each passed one view/all five dbt tests in
  71.852/66.875s. Retained
  .artifacts/dbt/2370e48f4fb648a08f029705a4f58d42 and .artifacts/dbt/e105a4fee0d344829b92270c0766a7bf.
- Physical/access: two read-only tests passed. All 33 parent fields/lineages,
  all per-order child counts/sums/warnings/presence and independently guarded raw
  aggregate totals conserved. Exact 49 native types/typmods/collations, private
  actual login/group/verify-full TLS/owner and API/public/reader SELECT denials passed.
- Mart has 99,441 orders, 112,650 items, 103,886 payment components, 99,224 review
  pairs and 547 multiple-review orders. Missing-family orders:
  items 775, payments 1,
  reviews 768; missing amounts NULL, counts zero.
- Exact source sums remain price 13591643.70, freight
  2251909.54, payments 16008872.12.
  Warning totals 0/4 items, 2/9/3 payments, 0 reversed reviews unchanged.
- Repeat preserved relation identity/owner/grants; password absent from both retained
  artifacts. Database 287,337,619 bytes below 400M. Suite timings include
  tests and are not consumer latency; measured plans/performance remain M5.
- Source dc81385 published clean before first build, complete 13-file staged/history
  secret scans passed (history 64 commits after source). Acceptance five-file staged-content/pre-commit history scans passed; final
  documentation review approved after minor continuation/status corrections.
  Rescan corrected staged contents, then post-commit history and clean/upstream Git.
- Historical M4 full evidence: docs/*-verification.json and matching model guides.
  Review latest offline 1283/native 52/physical 2/first+repeat 14 dbt tests documented
  at 1b67dc5; other model-specific details remain in their own dated guides.
- Full source/frontend/dependency advisory gates last passed 2026-09-22, not rerun for
  unchanged inputs. E2E/deployment/full governance audit NOT RUN. Unmodified
  check.ps1 deletes resources; use retained checks or obtain deletion permission.

## Current Repository Condition

CLEAN / STABLE at this acceptance checkpoint after final commit/status verification.
M4 COMPLETE; M5 mart computation verified; larger Phase 3 SAFE TO RESUME.
No known failed checks or partially implemented next unit. Reader SELECT is still
denied pending its scoped access unit; examples/plans/recovery are not yet verified.
No source reload, migration/dependency/credential mutation, deletion, merge or deployment.

## Incomplete Work

- M5 scoped reader grant/effective access; reliable technical examples; measured
  consumer query plans/performance; reconstruction/recovery proof and final handoff.
- Recommended Phase2 pandas parser debt: accepts nonpadded dates/leap-second rollover/
  now/today. Strict warehouse guards mitigate; fix before a new source version.
- Recommended precise API double transport: extra_float_digits=0 rounds text float8
  output. Stored precision proved via binary fetch/float8send; future coordinate API
  reads need binary or reviewed output configuration before use.
- Carry documented E01-E10 audit/revisit/release gates in Phase 1-2 audit/standards.
  Any later duration requires present ordered source events; no eligibility invented.
- Governance audit and required corrections only after verified Phase 3, before Phase 4.
  Git is not a database backup; protected retention/recovery before shared/irreplaceable data.

## Exact Next Actions

1. Check usage and clean/upstream Git against this acceptance; read warehouse/
   migrations/0001_foundation.sql and docs/order-components.md. Confirm reader
   currently has marts USAGE only and mart SELECT is denied. Read the accepted
   mart SQL/YAML/aggregate JSON; no M4 rebuild/source reload/reprovision needed.
2. Implement the narrow versioned approved-mart SELECT grant, applied only after
   the model exists. Verify effective reader SELECT and denied raw/core/writes/
   other schemas/API roles under the admin-assumed reader capability, without
   adding unnecessary credentials or blanket defaults. Update physical access
   expectations and reconstruction sequence; test/checkpoint the access unit.
3. Write reliable technical SQL examples (no business KPI policy), measure actual
   query plans/performance and capacity. Optimize only from evidence; recheck
   storage/rebuild overlap before considering materialization under ADR 0004.
4. Prove reconstruction/recovery from retained source/versioned migrations/dbt;
   review resource-destructive actions before requesting specific permission.
5. Complete Phase 3 verification/handoff/checkpoint. Only then perform comprehensive
   governance audit/required corrections before Phase 4. Carry release/debt gates.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Clean published resume
  baseline 1b67dc5; source dc81385 published clean before live build. Acceptance
  checkpoint is the containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
  Verify clean/upstream after publication and on resume; no merge/deployment.
- Complete staged-content/history scans required before publication, history again
  after commit. Retain outputs; disable auto Git cleanup. Checkpoint includes exact
  continuation and aggregate evidence; no need for export/source copy artifacts.
- Latest actual usage 37% five-hour/90% weekly remaining, 2026-10-04.
  Account-wide observation, not task-cost prediction; recheck before another unit.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
# Next unit: inspect the existing reader foundation and approved mart contract.
Get-Content warehouse/migrations/0001_foundation.sql
Get-Content docs/order-components.md
# Optional accepted-unit revalidation only; do not repeat implementation.
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select mart_order_components
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select mart_order_components
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:COMMERCE_WAREHOUSE_ORDER_COMPONENTS_INTEGRATION='1'
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_order_components_integration.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
```

Use customer-staging.md for retained warehouse/API/Ruff/mypy/parse workflow. Native
module is tests/test_warehouse_order_components_postgres_integration.py. Disable its
opt-in before full regression. Never print secrets/source records/driver diagnostics.
Resource deletion requires informed permission; product deletion follows authorized
ownership/confirmation/integrity requirements. Preserve C and new artifacts.
