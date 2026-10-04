# CommerceLens work state

Authoritative handoff. Updated 2026-10-04. Actual Git/files and verified results take
precedence over chat. Master plan, standards, execution protocol, deletion rule and ADRs apply.

## Project State

- Phase 3: M1-M4 COMPLETE; M5 mart, reader and technical query unit COMPLETE.
- Current milestone/task: prepare guarded full-graph reconstruction tooling, then
  prove the populated warehouse on a separately approved isolated native target.
- Objective: tested private warehouse under Free/views-first ADR 0004, retaining
  all source rows/warnings. Phase 4 EDA, Phase 5 KPI/API and public deployment remain later.
- Larger Phase 3 SAFE TO RESUME, roughly 10-15% implementation/verification effort
  remaining (reasoned range, not a time/model-count forecast). Exit audit effort unknown.

## Completed Work

- Phases 1-2 and professional-practices retrospective/remediation COMPLETE.
- M1/M2 contract/private foundation, migration replay, TLS/capability denials and
  disposable recovery checks verified 2026-09-21.
- M3 nine immutable tables/1,550,922 rows with full text/content/hash/money and
  deterministic repeat acceptance. No reload needed on the accepted target.
- M4 all nine staging, five dimensions, customer mapping and four facts COMPLETE
  at 1b67dc5. Model guides/receipts retain detailed acceptance.
- Mart computation accepted a74bd09: 99,441 orders/49 fields; independent children
  112,650 items/103,886 payments/99,224 reviews; 547 multiple-review orders.
  Missing families 775/1/768 retain zero counts/false presence/NULL amounts.
  Exact price/freight/payment sums 13591643.70/2251909.54/16008872.12.
- Reader accepted 7b3cc8c after explicit NOINHERIT role correction cc29398:
  exact mart SELECT, source/write/off-target/API/PUBLIC/MAINTAIN denials and
  compatible rebuild identity/owner/ACL/default preservation verified.
- This session: three aggregate-only total/month/bound-period SQL examples,
  native independent result oracle and bounded read-only measurement tool.
  Source checkpoint c01ee79 published clean before actual database checks.
  Native results, physical partitions and six measured plans now accepted.
- A/B/D cleanup completed earlier at 177c71d. Retain C fallback/three drafts and
  generated artifacts. No new obsolete resource identified; no deletion this session.

## Files

- Created warehouse/queries (three SQL + README), scripts/measure_warehouse_queries.py,
  two query tests, docs/warehouse-query-examples.md, warehouse-query-verification.json
  and warehouse-reconstruction-plan.md.
- Modified README, phase-3-plan, order-components and WORK_STATE to record acceptance.
- No files deleted/renamed; no dataset, model, migration, dependency, credential,
  environment, API/UI, materialization or deployment change. Artifacts retained.

## Technical Decisions

- Examples expose the same 33 aggregates without child joins, identifiers, review
  text, official revenue/GMV, status eligibility, selected review or EDA findings.
  Count zero is distinct from absent SQL NULL money and measured real zero.
  Literal C status groups and timezone-naive observed months remain unchanged;
  bound dates use inclusive-start/exclusive-end midnight. Warnings may overlap.
- Measurement uses verify-full TLS/private admin only to assume NOLOGIN reader,
  repeatable-read READ ONLY/forced rollback, SQL55s/lock5s, fixed three queries,
  one result read + two serial EXPLAIN ANALYZE TIMING OFF samples. Full plans
  remain ignored; published summaries contain no source rows/plan conditions.
- Q01 IMPORTANT before API analytics: roughly 4-9s cached server execution, spills
  and inaccurate estimates. Accepted bounded development evidence, not interactive
  readiness/SLO/cold-cache/concurrency proof. Future actual API workload/budget
  must justify statistics/indexes/materialization/caching within capacity. No tuning now.
- Parent buffers already include children; summed disk stats are not peak storage.
  Block size unmeasured; no temp-byte conversion. TIMING OFF cannot rank node seconds.
- Free/views-first remains: raw367M/database400M. Database287,345,811 bytes;
  size alone does not prove WAL/temp headroom. Native capability proof does not
  verify authentication for a future reader login; no such credentials provisioned.
- Fresh populated proof requires isolated native target: duplicating source in
  accepted database exceeds capacity. No local server/container tools found.
  Fresh Free Supabase eligibility/project creation/upload/retention not yet approved.
  Fixed full-graph bootstrap still needs guarded tooling because eager selected
  tests may reference unbuilt models. Never weaken current acceptance or TLS.

## Validation

- Query offline11 passed. Retained warehouse/API1394 passed /1000 deliberate
  live skips, 34.31s; known AnyIO alias warning. Ruff lint/format154 files and
  mypy23 implementations + measurement script passed. Optional-fetch/import
  defects corrected before published source checkpoint; no unresolved source failure.
- Query native11 passed in18.05s: all actual SQL/all33 fields/native metadata,
  empty/NULL/zero/warnings, literal groups, half-open/leap/midnight periods,
  UTC/Honolulu and large exact numeric headroom matched independent oracle.
  Typed read-only CTEs, restricted session, no warehouse fixture/data/object writes.
- Physical measurements complete:true; source totals/all-month partition and
  January status partition reconciled. Fresh connection verified unchanged mart
  OID/owner/ACL/defaults and database287,345,811 bytes. Scoped six-plan summary
  review passed. Admin/transformer passwords absent from all retained outputs.
  Receipt docs/warehouse-query-verification.json; full plans retained under
  .artifacts/warehouse-queries/55a9b9bf2d184a2bb61c6520d539d1d2.
- Server samples: totals8.645/8.192s, month7.030/6.994s, period3.985/3.972s.
  Initial client reads11.158/7.045/4.809s. These are serial development samples only.
- Prior reader: six read-only checks; persistent/repeated exact grant; compatible
  mart rebuild one view/five dbt checks in65.783s, post-build physical check passed.
  Other historical mart/M4 results remain in dated guides/receipts.
- Query source staged-content/history scans passed (69 commits after source).
  Acceptance seven-file staged-content/history scans passed before commit. Verify
  post-commit history scan and clean upstream after publishing this checkpoint.
- Full source/frontend/advisory gates historical2026-09-22, unchanged/not rerun.
  Populated reconstruction, E2E/deployment and full governance audit NOT YET RUN.
  check.ps1 deletes resources; use retained checks unless deletion approved.

## Current Repository Condition

CLEAN / STABLE expected after containing acceptance checkpoint and publish; verify
actual Git on resume. Query unit COMPLETE, larger Phase 3 SAFE TO RESUME. No live
measurement in progress or uncertain database change. Preserve all evidence.

## Incomplete Work

- Fixed full-graph/isolated configuration/target guards and complete manifest
  coverage tooling, then separately approved fresh-target populated reconstruction,
  full reconcile/repeat/access/query/size evidence and final M5 handoff.
- Q01 measured latency/spills; review before future API analytics, not silently ignored.
- Phase 2 pandas parser accepts loose dates/leap rollover/now/today; strict
  warehouse guards mitigate. Revisit before new source version.
- Future precise-coordinate API: extra_float_digits=0 rounds text float8; stored
  precision proved binary. Use binary or reviewed output config for that consumer.
- E01-E10 release/revisit gates remain. Git is not database backup; establish
  protected backup/retention/recovery before shared or irreplaceable data.
- Required comprehensive governance audit/corrections only after verified Phase 3,
  before Phase 4. Not performed prematurely; its effort is unknown.

## Exact Next Actions

1. Inspect src/warehouse/dbt_runner.py and docs/warehouse-reconstruction-plan.md;
   prepare the smallest fixed twenty-view/full-enabled-test bootstrap path with
   isolated purpose files, explicit expected target and protected-target rejection.
   Validate offline dispatch/failure/manifest coverage before a live target exists.
2. Check actual Free eligibility and obtain specific new-target/upload/retention
   approval after concrete tooling review. Preserve existing credentials/database.
3. Follow reconstruction plan migration/provision/load/repeat/full graph/post-model
   grant/physical/source/query/access/capacity order. Preserve failed attempts.
4. Finish Phase 3 handoff, then required governance audit/corrections/regressions
   and debt recording before Phase 4. Do not redo completed accepted warehouse units.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Resume baseline7b3cc8c;
  query source c01ee79. Acceptance is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md.
- Verify clean working tree and HEAD/upstream equality after publish/on resume.
  Disable auto Git maintenance, stage exact files and scan full content/history.
- Latest actual account-wide usage67% five-hour /81% weekly remaining2026-10-04;
  observation, not task-cost prediction. Recheck before larger new units.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
Get-Content docs/master-plan.md
Get-Content WORK_STATE.md
Get-Content docs/warehouse-reconstruction-plan.md
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
# Optional accepted query revalidation, not required to repeat on unchanged source:
$env:COMMERCE_WAREHOUSE_QUERY_EXAMPLES_INTEGRATION='1'
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_query_examples_postgres_integration.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -B -m scripts.measure_warehouse_queries --run
$env:COMMERCE_WAREHOUSE_QUERY_EXAMPLES_INTEGRATION='0'
```

See customer-staging.md for retained regression/static gates, mart-reader-access.md
for fixed grant procedure. Never log secrets/source records/driver diagnostics.
Project-resource deletion requires informed permission; legitimate authorized
product deletion remains supported. Preserve C and generated artifacts.
