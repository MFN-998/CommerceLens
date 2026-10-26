# Phase 5 — KPI and analytics layer

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

2026-10-24 three-view diagnostic preparation is verified offline. The retained
runner now includes full item-mart equivalence and independent failure/restoration
guards. Native execution was deferred at the usage reserve; no database changes.
See [preparation evidence](phase-5-three-view-preparation-verification.json) and
WORK_STATE for the exact execution step. Phase 5 remains incomplete.

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

Started 2026-10-05 in separate chat 01a10ae9-ebc3-74b3-8c42-018a1c90f7bf.
Verified resume: Phase 4 exit deaa4dd, successor metadata75f5335, clean/upstream0/0.
Phases 1–4 and governance remain COMPLETE / VERIFIED. Phase 5 is IN PROGRESS.

Latest source checkpoint a2a9715 consolidates duplicate child aggregation through
a shared macro, preserving all49 technical and70 KPI output fields. Offline1942
tests pass. Native13syntheticcases and full99441row/70field equivalence nowpass;
default-planner overview stilltimesout57014. Independentrollback/accesspassed.
See [native evidence](phase-5-aggregate-reuse-native-verification.json).
The local planner variant completed at10.286s and767246336 temporary bytes;
both budgets still fail, with verified rollback. See [planner evidence](phase-5-aggregate-planner-verification.json).
Next reduce remaining repeated order context using the executed plan. Neither
candidate is adopted. Full Q01 and consumer reconciliation remain pending.

2026-10-21: rollback-only index trials failed Q01 time/spill budgets; neither is
adopted. Postchecks verified rollback. See phase-5-index-probe-verification.json.
Certifi advisory E12 is resolved in the lock and patched retained Python environment;
see [dependency evidence](phase-5-certifi-verification.json) and development setup.
Next target repeated query/view work before full representative Q01 and consumer reconciliation.

Current 2026-10-20 checkpoint: both native builds, full-source comparisons,
fractional-review diagnostics and the remaining 18 native model-edge cases pass.
Actual upstream money aggregation is included; metadata remains unchanged.
See [edge evidence](phase-5-native-edges-verification.json), prior linked source
and review evidence, and WORK_STATE. Model-edge acceptance is complete.
Restricted reader grant/catalog/denials and positive view projections also pass;
see [access evidence](phase-5-reader-verification.json). Sixteen representative cases,
private parameter/model provenance and expensive overlapping client requests are now
implemented and tested offline. Next: native Q01 and independent consumer/dashboard
contract reconciliation. The first native overview read failed; three targeted
planner/CTE experiments also missed time/spill budgets and were not adopted.
See [Q01 diagnosis](phase-5-q01-diagnosis.json). The subsequent normalized-identity
index experiments above are complete and rejected; query/view refactoring is next.
Phase5 is incomplete.
Do not repeat accepted builds or model checks merely to resume.

Candidate implemented 2026-10-22: the item fact sources purchase timestamp and order
lineage directly from `stg_orders`, removing the unused customer enrichment from
its dependency path. The complete 15-field contract and literal LEFT JOIN remain.
Portable tests compare against the actual order fact with complete, partial and
absent customer mappings. Separate staged/core fixtures preserve the independent
fact-order reconciliation oracle and reject differing clocks, lineage or multiplicity.
Duplicate customer maps remain invalid and blocked; universal equivalence for an
invalid upstream graph is not claimed. The real offline parse asserts the new
model dependencies and unchanged reconciliation dependency on `fact_orders`.

See [offline candidate evidence](phase-5-item-context-verification.json).
Native full-source equivalence now passes: all 112650 rows/all 15 fields, exact
money and parent grain. Default-planner overview timed out; the candidate with
transaction-local nested loops discouraged completed in 12.540s with 784498688
temporary-traffic bytes, failing BOTH budgets. Independent rollback/access checks
passed after every attempt. See [native evidence](phase-5-item-context-native-verification.json).
The recovery warehouse still contains the previous accepted view. Three new native
oracle-divergence cases remain unrun. Neither adoption nor Q01 acceptance is claimed.
Next inspect repeated child aggregates/spills in the retained executed plan and
prepare a minimal reuse refactor with portable semantic checks before another
bounded native probe. Preserve coverage and purchase-cohort boundaries. The selected
runner remains limited to KPI marts; defer the similar item-mart change.

## Atomic milestones

1. Define versioned KPI policy and dictionary before implementing metrics.
2. Implement reusable view-based analytical marts and independent synthetic tests.
3. Measure actual query projections/filters/concurrency/plans and response/resource
   budgets; resolve Q01 before accepting API-facing analytics. Tune only on measured
   need under ADR0004, with explicit capacity and compatibility verification.
4. Implement bounded parameterized query contracts and exact response serialization;
   verify executive/trend/category/seller/geography consistency independently.
5. Verify native results/access, regressions and evidence; publish Phase 5 exit,
   then STOP and ask the owner for further instructions before starting Phase 6.
   Owner clarification dated 2026-10-22 overrides the earlier automatic transition.

Current implementation: M1 dictionary, M2a order and M2b item views, the selected
runner, bounded query/serialization contracts and measurement supervision are
implemented. The closed offline graph is22 models/304 tests. Both native builds
passed on2026-10-16; historical full Phase3 evidence remains unchanged.

The2026-10-17 item timeout was resolved by transaction-local full-consumption
cursor planning; the2026-10-18 read-only acceptance receipt also verifies final
metadata and source integrity. Timing is whole comparison time, not Q01 latency.

After resolving the measured first-overview failure, run the full prepared Q01
workload and independent consumer reconciliation. Preserve the private
recovery target, NOLOGIN/NOINHERIT reader and exact source contracts.
Phase 6 owns HTTP/database/UI integration, actual consumer authentication and exposure.
Phase 7 owns customer360/RFM/cohorts; Phase 8 owns predictive features/models.

## Verification and safety

Preserve ADR0003 grains/lineage/naive clocks/exact money/literal ZIP identity and
all29 warnings. Preserve both projects, private recovery settings/CA, datasets,
C fallback/three drafts and every artifact. No reload/reacquisition/credential swap,
merge/deployment/paid upgrade or unapproved project-resource deletion.
Reader stays NOLOGIN/NOINHERIT, mart-only. Native development capability checks
are not actual consumer authentication, public security or populated backup/PITR.
Q01 and E01–E10, source-version/date, coordinate, backup/auth/exposure/release gates
remain in governance-audit.md. Original Next16.3.5 is not patched-toolchain evidence;
use approved isolated16.3.8 only if frontend checks become applicable.

Account observation at resume: 28% five-hour/51% weekly remaining; shared, not reserved.
Use installed locked tools, unique retained outputs and secret-safe fixed diagnostics.
No Phase 4 tests, analysis, audit or live warehouse verification has been rerun here.

## Draft preservation checkpoint — 2026-10-06

Bounded query/serialization and fixed mart-reader/native verification helpers are
drafted, not accepted. Every query currently depends on pending mart_item_kpis.
The selected native runner is also pending; build commands fail closed. Four
read-only synthetic PostgreSQL tests passed (including actual order-view SQL),
not a live model build or Q01 acceptance. No grants or API endpoints were added.
See WORK_STATE.md for exact verification and the usage-reserve stop/resume gate.
Historical M2a observations above retain their original scope/date.

## Access safeguard checkpoint — 2026-10-07

Published94db831 adds effective reader capability checks, transactional post-grant
assertions and attempted/committed failure evidence.16 focused cases and full
offline1733 passed/1004 native skips/one known warning; lint/format183 and mypy32
plus verifier1 passed. No native operations this session. Item mart and scoped
runner writes were not completed; graph remains21/292 and build commands fail
closed. Q01 requires deadline enforcement throughout, representative item filters
and pagination/concurrency, reproducible parameters/model hashes and independent
native coverage/review/lateness/cross-dashboard acceptance. No Phase5 exit claim.

## Item mart source checkpoint — 2026-10-09

M2b adds mart_item_kpis at retained (order_id, order_item_id) grain, preserving all
15 fact item fields and adding11 order/product policy/context fields. Literal
LEFT JOINs to unique order/product parents preserve item rows, exact price/freight,
missing amounts and categories without payment/review fanout. Missing parents stay
visible and fail acceptance. Native precision/types/coverage remain pending.

15 independent portable SQL cases pass. The closed offline graph now has22 models
and304 tests (12 new item tests);192 focused item/runner/graph tests pass including
the network-blocked real parse. Initial sandbox fixture PermissionErrors were
resolved by rerunning with filesystem access; no guard was weakened. The broader
regression gate and publication are recorded in WORK_STATE and the item receipt.

Next is a scoped isolated-target build/test runner for the two Phase5 marts, then
native grain/precision/coverage and reader denial acceptance. No full-graph rebuild,
original target credentials or completed-phase repeat is needed. Q01 improvements
and complete native/cross-dashboard query acceptance still precede Phase5 exit.
New frontend dependency findings are tracked as E11 in the governance audit;
historical runtime-zero advisory evidence must not be presented as current.

## Selected build/test tooling checkpoint — 2026-10-09

The isolated two-mart runner and native CLI dispatch are implemented.149 focused
runner/graph/access regressions pass. Target guards reject original/default or
ambient routing; full offline preflight and live graph signatures, invocation IDs,
exact selected results and zero failures are required. Unique artifacts and
unknown/verified committed-build evidence survive failures. The full regression
result and source hashes are in phase-5-selected-verification.json.

See [native guide](phase-5-native.md) for commands and recovery. No native build,
grant or workload measurement ran. Next is scoped build-order, inspect evidence,
then build-item and independent native acceptance; Q01 and Phase5 exit remain open.
Usage81% five-hour/42% weekly triggered preservation, with no new unit started.
