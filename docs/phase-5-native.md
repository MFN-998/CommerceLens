# Phase 5 isolated native verification

## Current checkpoint — 2026-10-21

2026-10-22 source update: `fact_order_items` now reads its unchanged timestamp and
lineage context directly from `stg_orders`. This candidate is verified offline only;
the deployed warehouse still has the previous accepted definition. No Q01 improvement
is claimed. Do not run `measure` as if the candidate were already deployed.

Next native unit requires a reviewed one-view diagnostic; the existing selected
runner's two-mart allowlist remains unchanged. First compare the full 15-field
candidate and deployed baseline as multisets over the same source, preserving
literal identities and checking counts, exact money and parent uniqueness. Retain
the original view definition and the exact candidate/source hashes. Only after
equivalence succeeds, test a fixed `CREATE OR REPLACE VIEW core.fact_order_items`
inside a force-rollback transaction, with original time/memory limits. Preserve
column types, OID, owner, ACL/options and all other view definitions; no DROP,
COMMIT, grant change, index change or full-graph build. Measure the unchanged overview
under the existing reader role. A fresh independent connection must verify restored
definitions, relation metadata, permissions and capacity after success or failure.
Review deadline/failure handling before execution. This diagnostic is not implemented
or executed yet; passing it would still require broader acceptance before adoption.

Owner gate: after Phase 5 is completely verified and checkpointed, stop and ask for
further instructions before creating or starting Phase 6 (2026-10-22 clarification).

Both rollback-only index experiments are complete and rejected: original planner
execution was cancelled; discouraging nested loops still took13.630s and789MB
temporary traffic. Three historical totals matched; full Q01 remains unaccepted.
Independent postchecks confirmed complete rollback and unchanged warehouse state.
See [index probe evidence](phase-5-index-probe-verification.json). Certifi E12 is
resolved in the lock and new retained environment; see
[dependency evidence](phase-5-certifi-verification.json). Target repeated query/view work; do not rerun these
failed experiments or adopt their indexes/settings as a fix.

Native Q01 now has a measured failure at the first overview read. Three targeted
rollback-only experiments completed but exceeded server time and temporary-disk
budgets; no candidate is adopted. See [diagnostic evidence](phase-5-q01-diagnosis.json).
The later normalized-identity index diagnostics above are also complete and rejected;
do not blindly rerun the full workload or relax its limits. All accepted builds,
source comparisons, model edges and reader access remain valid.

Read-only index preflight passed for normalized order/customer/product identities.
Estimated indexes total22.88MB; a double build allowance stays below the existing
raw/database ceilings. Actual index size, build/WAL headroom, planner benefit and
rollback remain unverified. No index was created; the evidence receipt records
the preflight and exact next diagnostic boundary.

Both builds, full-source comparisons and native model edges are verified.
Restricted reader grants and separate catalog/denial/projection checks now pass.
See [model-edge evidence](phase-5-native-edges-verification.json) and
[reader evidence](phase-5-reader-verification.json). Do not repeat accepted
builds, comparisons or grants merely to resume. Representative workload preparation
is implemented and verified offline; native Q01 optimization and independent consumer
reconciliation remain pending.
Phase5 remains incomplete; no consumer authentication or public exposure is certified.

The restored recovery project's direct hostname failed DNS. Its dashboard's
IPv4 session-pooler route passed with existing credentials and verify-full TLS;
only private recovery admin/transformer routing was updated, with protected
backups retained. No original-project settings or passwords changed.

The measurement CLI now supervises all database stages under one600-second
budget, reserving2 seconds for worker cleanup. Connection/statement limits shrink
with remaining time; fixed stage markers survive interruption. Sixteen deterministic
cases now include existing eligible seller/product filters, missing category, combined
category/state and second pages for sellers, products and days. Source checksums and
required populations must validate before measurements begin.

Exact requests, bound identities and source provenance stay in ignored
`workload-private.json`. Source files and deployed view definitions are hashed before
and after the run; settings and per-query hashes bind the result to its inputs.
Client timing includes connection acquisition, role setup, serialization and close.
Separate synchronized seller/product requests must overlap and meet the unchanged
budgets. Overlap describes client fetch/serialization intervals, not a server trace.
Result-shape checks establish representative populations, not KPI correctness.

After a measured fix and its regression checks, with sufficient usage reserve,
rerun the bounded read-only measurement:

```powershell
.artifacts/python/certifi-20261021-01/Scripts/python.exe -B -m scripts.phase5_native measure --settings-root 'D:\My Projects\CommerceLens-Reconstruction' --expected-project-ref histbcmlctxmtxusfbzt
```

Inspect retained stages on failure; do not repeat blindly or tune without measured
evidence. All16 cases, the concurrent pair, budgets and final identity/provenance
checks must pass before Q01 acceptance. The diagnostic failure has not satisfied it.

## Scoped build and recovery reference

The selected runner supports only `mart_order_kpis` and `mart_item_kpis` on an
explicit isolated test target. It parses the complete closed graph offline,
builds only the selected view, and requires all eagerly selected tests to pass.
Test-only operations run those checks without rebuilding. It never expands to
ancestors, changes credentials, reloads sources, retries, or deletes artifacts.

Use the existing recovery root and target recorded in
[reconstruction evidence](warehouse-reconstruction-verification.json). Recheck
account reserve and the latest WORK_STATE before any native invocation. The
original project and ambient WAREHOUSE/PG routing variables are rejected.

Historical build command (both builds already verified2026-10-16; do not rerun):

```powershell
.venv/Scripts/python.exe -B -m scripts.phase5_native build-order --settings-root 'D:\My Projects\CommerceLens-Reconstruction' --expected-project-ref histbcmlctxmtxusfbzt
```

The order and item receipts are recorded in phase-5-native-build-verification.json. `test-order` and `test-item` rerun
only the selected checks. Do not invoke the historical full-graph build path for
these additions. A native operation has not passed merely because tooling tests
or the offline graph parse passed.

Subprocess stdout/stderr and file logs are disabled. Each run retains unique
preflight/live artifacts under the isolated root's `.artifacts/dbt-selected`,
and the wrapper retains before/after metadata under repository `.artifacts/phase-5`.
The runner checks the entire preflight/live graph contract, distinct invocation
identity, exact selected result set and zero test failures. SQL/lock/idle limits
remain60/10/60 seconds; setup/selected subprocess limits remain120/180 seconds,
one dbt thread and no retry. These limits are not Q01 consumer latency acceptance.

The preserving view materialization can commit before tests finish. Failure
evidence distinguishes no dispatch, an uncertain committed build after dispatch,
and a verified committed build followed by a receipt/metadata failure. Inspect
the selected relation and retained evidence before retrying. Do not drop, reset
or assume rollback; Git cannot roll back the database. Permission or disk failures
can prevent a receipt write, so retain the exception's fixed recovery facts too.

After native model checks, verify independent precision/grain/coverage, reviews,
calendar lateness and dashboard reconciliation. Extend and verify reader catalog
and denial checks before Q01. The current `verify-totals` checks only three
historical totals and does not satisfy full KPI acceptance. The prepared Q01 workload,
concurrency and provenance checks still require successful native execution.
No consumer authentication or HTTP/UI
integration is certified here; those remain Phase6.

## Full-source comparison planning — 2026-10-18

The acceptance checker consumes every row of both already-built views. Read-only
EXPLAIN compared cursor_tuple_fraction0.1 and1.0; the default item plan contained
two costly nested loops that disappeared with1.0. Both plans substantially
overestimate cardinality, so estimated cost is not actual latency evidence.
The checker sets1.0 only inside its rollback-only transaction, retains1000-row
batches and unchanged SQL/whole-job limits, and records comparison elapsed time.
This follows [PostgreSQL cursor planning documentation](https://www.postgresql.org/docs/current/runtime-config-query.html).
It does not change database defaults or establish consumer-query performance.
The final native result and remaining acceptance scope belong in WORK_STATE and
the dated source-acceptance evidence; failed runs remain retained.
