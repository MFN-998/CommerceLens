# Phase 5 isolated native verification

2026-10-28: read-only15-plan diagnosis passed with independent restoration. Shared
mart estimates match across reader/transformer roles; raw/normalized item grouping
estimates87208 but staging/mart estimate200. Next isolate the WITH/subquery boundary
before statistics or model changes. See [evidence](phase-5-estimate-diagnosis-verification.json)
and [research](phase-5-estimate-diagnosis-20261028.md). No performance acceptance.


2026-10-26 follow-up: the same fixed reference-reuse query with normal planner
settings was cancelled during EXPLAIN ANALYZE. Full source equality and independent
restoration passed; no execution metrics or response check completed in this run.
See [default-planner evidence](phase-5-reference-default-planner-verification.json).
Next investigate the order/item-group estimates before a new statistics experiment;
no production adoption, full Q01 acceptance or Phase 6 transition.


2026-10-26: fixed overview reference reuse preserves full source and response
contracts and passes temporary traffic (504496128 bytes), but 17.579s fails the
10s limit. Independent restoration passed; no adoption. See
[verification](phase-5-reference-reuse-verification.json) and
[primary-source research](phase-5-performance-research-20261026.md).
Next review normal-planner measurement of the same query; full Q01 remains open.


2026-10-25 full-source verification passed for the shared projection. Its overview
sample met the time limit at7.917s, but565272576 temporary bytes exceeded budget.
A scope-inlining variant preserved the full response and restored all state, but
failed both limits at14.057s/542613504 bytes. Neither is adopted; fullQ01 remains
open. See [full-source evidence](phase-5-shared-projection-full-source-verification.json),
[scope evidence](phase-5-shared-projection-scope-verification.json) and WORK_STATE.

2026-10-25: all 50 typed PostgreSQL fixtures passed for the shared item/order
projection. Independent catalog/access/settings checks passed, with unchanged
database/raw sizes. Full-dataset equivalence and performance for this candidate
remain pending. See [native evidence](phase-5-item-projection-native-verification.json)
and WORK_STATE for the next three-view probe preparation.

2026-10-25 shared item/order projection candidate now passes all offline checks:
1986 tests, lint/format/types and real dbt graph/selected-runner verification.
Native and performance verification of this new macro remain pending. See
[shared projection evidence](phase-5-item-projection-verification.json) and WORK_STATE.

2026-10-25: the combined three-view diagnostic passed all full-source 15/70/26-field
comparisons and independent restoration. Overview11.831s /631332864 temporary
bytes still fail both budgets; no candidate adopted. See
[three-view native evidence](phase-5-three-view-native-verification.json) and
WORK_STATE for the remaining plan-driven optimization and acceptance steps.

2026-10-24 native fixture update: all50 item-model/reconciliation cases passed,
including41 new typed cases. Fresh independent catalog/access restoration passed;
no persistent adoption. Full-source equivalence/performance remains pending.
See [native fixture evidence](phase-5-item-mart-native-fixtures-verification.json)
and WORK_STATE for the next guarded probe. Earlier offline-only status is historical.

2026-10-24 source candidate: item KPI parent identity/status now comes directly
from staged orders; independent full-row reconciliation retains fact_orders.
All 26 fields are preserved. Offline 1986 tests pass; native checks/performance
remain unrun for this candidate. See [offline evidence](phase-5-item-mart-context-verification.json)
and WORK_STATE for the exact next unit. No persistent adoption or Q01 acceptance.

2026-10-23: the combined item-context/KPI candidate with a local planner setting
completed at 11.873 seconds and 700751872 temporary-traffic bytes: both budgets
still fail. All 112650 item rows/15 fields and 99441 KPI rows/70 fields matched;
fresh restoration/access checks passed. Neither candidate is persistently adopted.
The first attempt stopped in preflight with unknown cause and verified restoration;
a revision added fixed-stage diagnostics without weakening guards.
See [combined native evidence](phase-5-combined-native-verification.json) and
WORK_STATE for the next step. New E11/E13 advisory gates are recorded in
[the current audit evidence](phase-5-advisories-20261023.json).

## Current candidate — shared child aggregation, 2026-10-22

Published source checkpoint a2a9715 consolidates child counts, amounts, warnings,
coverage and review inputs. Technical output remains 49 columns; KPI output stays
70 columns. See [offline evidence](phase-5-aggregate-reuse-verification.json).
All13 native synthetic cases passed. The rollback-only KPI replacement matched
all99441rows/all70fields and preserved native column/catalog/access contracts.
Default-planner overview EXPLAIN ANALYZE timed out57014; no timing/spill result is
accepted. Fresh independent rollback and access checks passed. Raw size was
275988480 bytes and database size was 287569587 bytes, within ceilings. Database
size increased 32768 bytes; no cause is asserted. No candidate was adopted.
See [native evidence](phase-5-aggregate-reuse-native-verification.json).
The subsequent local planner variant completed at10286.49ms and767246336 temporary
bytes, failing both budgets. Full equivalence and independent rollback passed;
no persistent adoption. See [planner evidence](phase-5-aggregate-planner-verification.json).
Next use the executed plan to reduce remaining repeated order-context work;
full Q01 and consumer acceptance remain pending.

## Previous diagnostic — item context, 2026-10-22

The source candidate reads item timestamp/lineage directly from `stg_orders`.
A reviewed one-view, rollback-only diagnostic now verifies all 112650 source rows
and all 15 fields against the deployed baseline as multisets, with zero differences,
exact money, parent uniqueness and unchanged column/ownership/access metadata.
The default-planner overview still timed out (SQLSTATE 57014). The same candidate
with only transaction-local `enable_nestloop=off` completed at 12540.395ms and
784498688 temporary-traffic bytes: BOTH 10000ms/536870912-byte budgets failed.
Three historical totals matched; this is not full consumer reconciliation or Q01.

Fresh independent postchecks verified restoration after every attempt, including
view definitions, relation/column/dependency metadata, indexes, reader access and
planner settings. Final raw/database sizes were 275988480/287536819 bytes, within
existing ceilings; total database size increased 8192 bytes during the final run.
No cause is asserted and rollback does not prove absent WAL/filesystem effects.
An earlier pre-DDL abort caught an 8192-byte difference from historical database
size; the reviewed guard permits only that total-size variation within capacity,
while keeping raw size, identities, indexes, permissions and definitions strict.

See [native candidate evidence](phase-5-item-context-native-verification.json).
Nothing was adopted; the recovery warehouse retains its previous accepted views,
and the selected runner's two-mart allowlist is unchanged. Native candidate edge
cases remain unrun. Do not measure as though the candidate were already deployed.
Next inspect repeated child aggregates and spill-producing nodes in the retained
executed plan, then prepare a minimal reuse refactor with portable semantic checks.
Preserve independent child aggregation, coverage, literal identities and purchase
cohorts. Review another bounded native probe only after those checks. Do not repeat
the rejected experiments, relax budgets or infer acceptance from three totals.

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

Historical read-only index preflight estimated 22.88MB. The subsequent completed
rollback-only builds used 13770752 bytes and failed the performance budgets, as
recorded above; the preflight is not an outstanding action.

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
