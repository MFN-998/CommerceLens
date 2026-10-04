# CommerceLens work state

Authoritative handoff. Updated 2026-10-04. Actual Git/files and verified results take
precedence over chat. Master plan, standards, execution protocol, deletion rule and ADRs apply.

## Project State

- Phase 3: M1-M4 COMPLETE; M5 mart, reader and technical query unit COMPLETE.
- Current milestone/task: guarded full-graph source remains COMPLETE at edf072b.
  Isolated migration/load/provision/grant dispatcher COMPLETE and verified;
  final-check adapter COMPLETE and verified offline;
  then prove the populated warehouse on a separately approved isolated native target.
- Objective: tested private warehouse under Free/views-first ADR 0004, retaining
  all source rows/warnings. Phase 4 EDA, Phase 5 KPI/API and public deployment remain later.
- Larger Phase 3 SAFE TO RESUME, roughly 10-15% implementation/verification effort
  remaining (reasoned range, not a time/model-count forecast). Exit audit effort unknown.

## Completed Work

- Current session: recovered clean published edf072b with no partial source;
  workflow checkpoint590863b records new-chat requirement. Phase 3 stays here;
  only after verified completion create audit chat, then each later phase separately.
- Isolated one-step dispatcher wraps existing migration/load/provision/grant and
  graph helpers, with outside-repo test settings/exact fresh reference, protected
  target rejection, contained absolute CA, credential ACL protection and no
  ambient WAREHOUSE/PG routing. Fixed secret-safe receipts only after clean exit;
  no automatic retry/cleanup. No fresh target or upload performed.
- Final-check adapter reuses 20 physical modules/native-query/reader oracles in
  isolated child: exact 22 files/current 42 cases, purpose bindings/CA guarded, no
  inherited plugins/conftest/cache, private outputs discarded, complete three-phase
  case coverage required. Atomic safe receipts retained, no retry/cleanup.
- Non-secret browser draft CommerceLens-Recovery/Free/Tokyo/DataAPI off is prepared,
  owner explicitly APPROVED2026-10-04: one Free/Tokyo project, DataAPI disabled,
  nine unchanged source tables/1,550,922 rows and retention for reconstruction.
  Creation/private password entry/submission handed to owner, dashboard confirmation
  pending; no new project or isolated configuration yet verified. Free eligibility
  not guaranteed; no paid commitment or project deletion authorized.

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
- Prior session: three aggregate-only total/month/bound-period SQL examples,
  native independent result oracle and bounded read-only measurement tool.
  Source checkpoint c01ee79 published clean before actual database checks.
  Native results, physical partitions and six measured plans accepted at b82c7d7.
- Prior session's second unit: separate guarded full-graph callable/tests, exact20
  views/nine sources/all282 enabled tests, target/file/CA/artifact isolation and
  pinned preserving-view macro. Existing single-model runner remains unchanged.
- A/B/D cleanup completed earlier at 177c71d. Retain C fallback/three drafts and
  generated artifacts. No new obsolete resource identified; no deletion this session.

## Files

- Current acceptance unit adds src/warehouse/reconstruction_acceptance.py and
  tests/test_warehouse_reconstruction_acceptance.py; reconstruction/phase plans
  and this handoff updated after actual offline validation.

- Current unit adds src/warehouse/reconstruction.py and
  tests/test_warehouse_reconstruction.py; modifies reconstruction plan, phase-3
  progress and this handoff. Workflow unit changed AGENTS/master-plan/protocol.
  No files deleted/renamed, dependency/configuration/migration/model/data change.

- New recovery unit: src/warehouse/dbt_reconstruction.py and
  tests/test_warehouse_dbt_reconstruction.py; existing one-model wrapper unchanged.

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
  Fresh Free Supabase project/upload/retention approved2026-10-04; actual
  eligibility and created-target dashboard confirmation still pending.
  Full-graph source is now verified; eager one-model tests can reference unbuilt
  children, so recovery uses the fixed full dependency graph. Other operation
  dispatch and isolated acceptance source now verified; native proof pending. Never weaken current acceptance or TLS.
- Separate graph callable requires outside-repo purpose settings/test environment,
  explicit fresh reference/protected-target rejection and no ambient WAREHOUSE
  override. Fixed macros/source/model/test contracts and full result/invocation
  checks fail closed. Compiled macro dependencies may grow; definitions stay pinned.
  Graph1200s budget unproven; per-statement60s and one-thread/retries0 unchanged.
  Partial committed builds are preserved/inspected, never automatically cleaned.

## Validation

- Final-check+dispatcher 97 passed in 0.82s; retained warehouse/API 1578 passed in 43.26s,
  1000 deliberate live skips, known AnyIO warning. Ruff lint/format 160 files and
  mypy 26 implementations passed. Safe real collection verified42 current cases
  across22files without fixture/test execution. Scoped review passed; test cases
  are simulated subprocess/pytest evidence, not fresh native proof. No unresolved
  source failures. Dispatchera2bed4f complete-content/pre/post-history scans passed,
  published clean HEAD/upstream0/0. Final-check five-file complete staged-content and pre/post-history scans passed;
  c961aff published clean with HEAD/upstream0/0. No secrets found by these checks.

- Current dispatcher:293 focused passed27.24s; warehouse/API1534 passed37.97s,
  1000 deliberate live skips, known AnyIO deprecation warning. Ruff lint/format158
  files and mypy25 implementations passed. Fake connections verify purpose/root/
  CA/routing/file guards, side-effect order, retained partial files, failures and
  safe CLI responses; this is not fresh native proof. No live target accessed.
  Review found credential hard-link aliases could affect outside ACLs: corrected
  before protection/read;54 dispatcher tests passed0.44s afterward, static gates
  rerun passed, scoped reviewer confirmed. Both synthetic links retained.
- Workflow590863b complete staged-content plus pre/post-history scans passed,
  published clean HEAD/upstream0/0. Current five-file complete staged-content and
  pre/post-history scans must pass; verify clean upstream after this checkpoint.


- Recovery source: focused new/existing-runner 173 passed; warehouse/API
  1481 passed /1000 deliberate live skips. Ruff lint/format156 files,
  mypy24 implementations passed. Guarded real offline parse20/282/9 and historical
  build-manifest compatibility passed; simulated results are not live build proof.
  Missing/changed preserving macro and startup ValueError review findings corrected;
  target/containment/env/coverage/status/invocation/failure/retention cases verified.
  Initial sandbox run blocked retained fixture directories; approved rerun passed
  (173/23.87s; regression1481/38.24s). No source-test failure remained. Scoped final
  review passed both corrections. No accepted credentials/database access/live graph.
  Known AnyIO warning only.

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
- Query source/acceptance complete staged-content/pre/post-commit history scans
  passed; b82c7d7 published with clean tree/HEAD-upstream0/0. Recovery source four-file
  full staged-content/history scans passed before commit. Verify post-commit
  history scan and clean upstream after publishing the containing checkpoint.
- Full source/frontend/advisory gates historical2026-09-22, unchanged/not rerun.
  Populated reconstruction, E2E/deployment and full governance audit NOT YET RUN.
  check.ps1 deletes resources; use retained checks unless deletion approved.

## Current Repository Condition

CLEAN / STABLE at published c961aff confirmed; local tooling task COMPLETE.
Final preservation documentation is the containing checkpoint; verify Git on resume.
Local recovery preparation COMPLETE; new target approved; owner creation/private
configuration pending. Source acceptance and preserved baseline remain unchanged.
Accepted warehouse unchanged. Larger Phase 3 SAFE TO RESUME: fresh native proof
and final handoff pending; no uncertain live operation or interrupted build.
Preserve C, credentials/source data and all generated evidence.

## Incomplete Work

- Owner creation/dashboard confirmation of approved Free recovery project,
  isolated private configuration, then full populated reconstruction,
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

1. Await owner's dashboard-ready confirmation for approved CommerceLens-Recovery.
   Owner approval received2026-10-04 for Free/Tokyo/DataAPI off, all nine unchanged
   source tables and retention. Private new-password entry/submission handed off in
   preserved Supabase tab; do not request credentials in chat or re-ask this approval.
   Verify Free eligibility and created project/reference. If unavailable/paid upgrade
   required, stop for a reviewed alternative. No project deletion authorized.
2. Recover its actual project reference/connection/public CA details, then create
   isolated protected test-purpose configuration under the proposed outside-repo
   D:\My Projects\CommerceLens-Reconstruction root. Never change original purpose
   files or globally override WAREHOUSE/PG environment. Inspect version/empty state/
   initial capacity before unchanged migration/provision/load. Different PostgreSQL
   version requires boundary re-evaluation. Tooling complete; do not redo it.
3. Follow reconstruction plan migration/provision/load/repeat/full graph/post-model
   grant/physical/source/query/access/capacity order. Preserve failed attempts.
4. Finish verified Phase 3 handoff here; create a new CommerceLens chat for the
   required governance audit/corrections/regressions. After that gate, create a
   separate Phase 4 chat, and separate chats for each subsequent phase. Repository
   handoffs, not this long chat, carry context. Do not redo completed warehouse units.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Current resume baseline edf072b;
  query source c01ee79/query acceptance b82c7d7/recovery source edf072b; workflow
  590863b, dispatchera2bed4f and verified final-check sourcec961aff published.
  Pre-approval preservationfd28354 published clean; approved-target handoff
  checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md.
- Verify clean working tree and HEAD/upstream equality after publish/on resume.
  Disable auto Git maintenance, stage exact files and scan full content/history.
- Latest actual account-wide usage45% five-hour/67% weekly remaining2026-10-04.
   Earlier 99/75 at reset, 80/72, 72/71 and 47/67 before atomic units. These are observations,
   not task-cost predictions. Preserve the verified source checkpoint; native proof
   waits owner creation/private configuration. Recheck usage before any major live unit.

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
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_reconstruction_acceptance.py tests/test_warehouse_reconstruction.py tests/test_warehouse_dbt_reconstruction.py tests/test_warehouse_dbt.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
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
