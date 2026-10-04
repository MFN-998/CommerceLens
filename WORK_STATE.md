# CommerceLens work state

Authoritative handoff. Updated 2026-10-04. Read actual Git/files before resuming.
Master plan, engineering standards, execution protocol, deletion rule and ADRs apply.

## Project State

- Phase 3 Database/SQL/Analytics Engineering: M1-M4 COMPLETE; M5 in progress.
- Current milestone: technical SQL examples and measured query plans IN PROGRESS.
- Current task: three aggregate-only SQL candidates, native result-oracle tests
  and bounded read-only performance tooling being prepared. Source adopted; offline/static
  validation passed; native/performance NOT YET RUN; reader/mart baseline remains accepted. No source reload/redesign.
- Objective: tested private warehouse under Free/views-first ADR 0004, preserving
  all source rows/warnings. No Phase 4 EDA, Phase 5 KPI policy or public deployment.
- Larger Phase 3 SAFE TO RESUME; examples, performance, populated reconstruction
  proof and final handoff remain. Prior 10-20% remaining implementation estimate
  at M4 was a broad effort range, not a time forecast. Exit audit effort unknown.

## Completed Work

- Phases 1-2 and professional-practices retrospective/remediation COMPLETE.
  See docs/phase-1-status.md, phase-2-status.md, engineering-audit-phase-1-2.md.
- M1 contract/M2 private development foundation verified, including migration
  replay, TLS/capabilities/denials and disposable recovery checks (2026-09-21).
- M3 COMPLETE: nine immutable source tables / 1,550,922 rows; exact text, lineage,
  full-content/hash/money reconciliation and repeat. No reload needed.
- M4 COMPLETE at 1b67dc5: nine staging views, five dimensions, order-customer
  mapping and four facts. Detailed types/warnings/results in model guides/receipts.
- M5 order mart computation accepted a74bd09 after source dc81385: 99,441 orders,
  49 fields; independent item/payment/review aggregation avoids child fanout.
  Components 112,650 / 103,886 / 99,224; 547 multiple-review orders. Missing
  families 775 / 1 / 768, counts zero/presence false/amount NULL. Exact sums
  price 13591643.70 / freight 2251909.54 / payments 16008872.12; warnings retained.
- This session: fixed post-model SELECT grant/CLI, failure-boundary/native tests,
  reader guide and receipt. Corrected explicit NOINHERIT role activation after
  safe failed rehearsals; rollback, persistent/repeat grant and rebuild verified.
- Approved A/B/D cleanup completed 177c71d; retain C fallback/three drafts and
  generated artifacts. No new obsolete resource needing deletion identified.

## Files

- Current query unit created warehouse/queries (three SQL + README),
  scripts/measure_warehouse_queries.py, two query tests, docs/warehouse-query-examples.md
  and warehouse-reconstruction-plan.md. No dependency/model/data/configuration change.

- Created warehouse/access/mart_order_components.sql, src/warehouse/access.py,
  tests/test_warehouse_mart_access.py, test_warehouse_mart_reader_integration.py,
  docs/mart-reader-access.md and mart-reader-verification.json.
- Modified CLI, order-component physical access expectations, README,
  docs/phase-3-plan.md, order-components.md, warehouse-development.md, WORK_STATE.md.
- No files deleted/renamed; no upstream model, dataset, migration, dependency,
  credential, API/UI, materialization or deployment change. Scratch/.artifacts retained.

## Technical Decisions

- Fixed versioned grant follows model construction during reconstruction, separate
  from pre-model schema migrations. Transformer owns/grants the exact mart; no
  wildcard/default privileges, grant option or new reader login. Login guard first,
  explicit transformer SET LOCAL ROLE, target/ACL guards, grant, RESET ROLE.
- Guards fail closed for wrong session/owner/security_invoker/elevated reader/
  membership or excess schema/table/column/write/MAINTAIN/API/PUBLIC rights.
- Native existing-admin SET LOCAL ROLE proof verifies NOLOGIN capability, not
  authentication/session restrictions for a future reader login. Verify a future
  consumer login when needed; no premature credential provisioning.
- No access to raw/staging/core/ops or warehouse writes for reader. Intended SELECT
  uses view-owner underlying-table checks; not a multitenant/row-level boundary.
- Mart preserves all parent fields/source warnings; no canonical review/status
  eligibility or official KPI. Exact unconstrained numeric SUM; absence != real zero.
- Compatible replace preserves identity/owner/grants and commits before tests;
  failed acceptance is not rollback. Preserve artifacts/view; diagnose without DROP,
  full refresh, source reload or unapproved project-resource deletion.
- Free/views-first ADR 0004: database ceiling 400M/raw 367M. Measure storage,
  rebuild overlap and consumer plans before materializing. Size alone does not
  prove WAL/temp headroom. Restricted job logins and verify-full TLS unchanged.
- Runner parse/debug120s, one-model build/test180s; SQL60s/lock10s/idle60s,
  one thread/zero retries; safe errors/no sensitive row logging.

## Validation

- Query source/offline: 11 focused cases passed; retained warehouse/API1394 passed /
  1000 deliberate live skips. Initial script typecheck found two unchecked optional
  database fetches; explicit missing-result guards added. Import spacing corrected.
  Final Ruff lint/format154 files, mypy23 implementation files + one measurement
  script, diff whitespace and focused11 recheck passed. Native11 cases and
  physical measurements NOT YET RUN.

- Current query unit: scoped candidate source/harness reviews and AST/Ruff checks
  passed; adopted source runtime/full gates NOT YET RUN. All native fixtures are
  typed read-only CTEs; no persistent tables/rows or permission changes.

- Reader source: 17 focused cases passed. Retained warehouse/API: 1383 passed /
  988 deliberate live skips (before sixth native guard case). After role correction,
  focused 17 passed / six live skips. Ruff lint/format 148 files; mypy 23 sources passed.
  New native-test long line split; final scoped Ruff/format/diff checks passed.
- Scoped source/harness/doc reviews passed. Rehearsal initially failed safely:
  NOINHERIT login requires capability before mart inspection; post-command probe
  requires reactivation after RESET ROLE. No persistent grant from failed rehearsals.
- Corrected rollback rehearsal: SELECT true inside, false after; exact relation
  identity/owner/ACL restored and default privileges unchanged. Persistent and
  unchanged repeated grant passed using existing dedicated transformer.
- Six read-only reader checks passed in 19.50s: exact SELECT/49 types/aggregates,
  source/write/off-target schema/table/column/API/PUBLIC/MAINTAIN/grant-option
  denials and actual wrong-session helper P0001 rejection. No fixture/data writes.
- Compatible mart rebuild: one view/all five dbt checks passed in 65.783s,
  identity/owner/ACL/default grants preserved. Retained
  .artifacts/dbt/f87f492ec7fd4c78860e9ee8c87109b4; password absent in all outputs.
  Post-build physical metadata/access: one passed in 5.89s. Database 287,345,811
  bytes below 400M. Build/test timing is not consumer-query latency.
- Historical computation evidence: docs/order-components-verification.json;
  current access evidence: docs/mart-reader-verification.json. Historical pre-grant
  SELECT denial remains accurate at its date; new receipt supersedes current access.
- Prior computation:85 offline/171 focused/1370 regression(983live skips)/71 native/
  two physical passed; first/repeat five dbt checks in 71.852/66.875s, parse/Ruff/mypy passed.
  Other M4 details remain in dated model guides/receipts.
- Complete staged-content/history scans passed source/correction checkpoints;
  final documentation review approved after correcting the M5 status row.
  Acceptance seven-file staged-content/pre-commit history scans passed; final
  corrected-state rescan and post-commit history/clean-upstream confirmation are
  required before concluding.
- Full source/frontend/advisory gates last 2026-09-22, unchanged and not rerun.
  E2E/deployment/full governance audit NOT RUN. check.ps1 deletes resources;
  use retained checks or obtain permission. Known AnyIO alias warning only.

## Current Repository Condition

PARTIALLY IMPLEMENTED: query source/offline/static accepted; native/performance checks
pending. Accepted mart/reader/upstream foundation remains stable; no database
changes, model rebuild, dependency/configuration change or deletion.

## Incomplete Work

- Recovery feasibility confirmed: full populated proof requires a fresh isolated
  target; another landing in the accepted database exceeds storage ceilings. No
  local PostgreSQL/Docker server tools found. Separate Free Supabase target choice/
  eligibility/approval still missing. Fixed full-graph dbt bootstrap needs reviewed
  tooling because eager one-model tests can reference unbuilt children.

- M5 technical examples, measured consumer plans/performance, full populated
  reconstruction/recovery proof and final handoff. Governance only after verified
  Phase 3; fix Critical/relevant Important issues before Phase 4.
- Recommended Phase 2 pandas parser accepts nonpadded dates/leap rollover/now/today.
  Strict warehouse guards mitigate; revisit before new source version.
- Recommended future precise coordinate API: extra_float_digits=0 rounds text
  float8; stored precision verified binary/float8send. Use binary or reviewed output
  configuration before that consumer. E01-E10 release/revisit gates still apply.
- Git is not a database backup; protected backup/retention/recovery before shared
  or irreplaceable data. Future login authentication not yet applicable/tested.

## Exact Next Actions

1. Verify containing query-source checkpoint is clean/published. Run native11
   typed fixture cases, then serial read-only
   measurements via scripts.measure_warehouse_queries --run; retain all outputs.
2. Validate source totals/month/status partitions, inspect actual plans/spills,
   document views-first implications and checkpoint accepted query evidence.
3. Prove populated reconstruction against an isolated approved target with guarded
   migrations/load/model/grant order and complete reconciliation; never overwrite
   the accepted source or delete artifacts without permission. Then final M5 handoff.
4. Complete verified Phase 3, run required comprehensive governance audit/corrections
   and regressions, document debt, then Phase 4. Do not redo completed M1-M4/mart units.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged. Resume baseline
  7b3cc8c. Reader source 0f853c7/correction cc29398 published clean before persistent
  grant. Acceptance checkpoint is the containing commit:
  git log -1 --format="%H %s" -- WORK_STATE.md.
- Verify working tree/upstream clean after publish/on resume. Disable auto Git
  maintenance/cleanup, stage exact reviewed files, scan full contents/history.
- Latest actual usage 76% five-hour / 82% weekly remaining, 2026-10-04;
  account-wide observation, not task-cost prediction. New window reset; proceed in
  bounded verified milestones and recheck periodically.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
Get-Content docs/master-plan.md
Get-Content docs/order-components.md
Get-Content docs/mart-reader-access.md
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
# Optional accepted access revalidation only:
$env:COMMERCE_WAREHOUSE_MART_READER_INTEGRATION='1'
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_mart_reader_integration.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
# Disable native opt-ins before retained regression.
$env:COMMERCE_WAREHOUSE_MART_READER_INTEGRATION='0'
```

See customer-staging.md for retained warehouse/API/Ruff/mypy gates and reader guide
for recovery grant command. Never log secrets/source records/driver diagnostics.
Project resource deletion requires informed permission; authorized product deletion
remains legitimate. Preserve C and generated artifacts until specifically approved.
