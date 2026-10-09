# Phase 5 — KPI and analytics layer

Started 2026-10-05 in separate chat 01a10ae9-ebc3-74b3-8c42-018a1c90f7bf.
Verified resume: Phase 4 exit deaa4dd, successor metadata75f5335, clean/upstream0/0.
Phases 1–4 and governance remain COMPLETE / VERIFIED. Phase 5 is IN PROGRESS.

## Atomic milestones

1. Define versioned KPI policy and dictionary before implementing metrics.
2. Implement reusable view-based analytical marts and independent synthetic tests.
3. Measure actual query projections/filters/concurrency/plans and response/resource
   budgets; resolve Q01 before accepting API-facing analytics. Tune only on measured
   need under ADR0004, with explicit capacity and compatibility verification.
4. Implement bounded parameterized query contracts and exact response serialization;
   verify executive/trend/category/seller/geography consistency independently.
5. Verify native results/access, regressions and evidence; publish Phase 5 exit and
   create the separately authorized Phase 6 chat only after that exit gate.

M1 policy COMPLETE at35cb6dc. M2a order-view source/offline checks COMPLETE;
native acceptance and the rest of M2–M5 remain pending. Current source adds
mart_order_kpis (one order, preserving every original column) and12 independent
synthetic cases. Approved graph is explicitly21 models/292 tests in offline parse;
historical Phase3 native20/282 evidence is unchanged, not refreshed.

Current checks: full offline1683 passed/1000 deliberate native skips/knownAnyIO1,
42.75s; Ruff lint/format176; mypy29; offline dbt parse artifact
.artifacts/dbt/b126343ffb3a4e9b81360e1fde62b67b. Initial broad run failed the
expected closed graph guard; explicit model/schema allowlist and independent
fixed-graph fixture were extended, then the full suite passed. No suppression.

First next step: implement and independently test a narrowly selected build/test
path against the explicit protected isolated recovery target before native acceptance.
Do not invoke full-graph reconstruction merely to build this new view or use
original default settings. Existing reader grant guards accept only the technical
mart: extend explicit per-mart access verification only after model acceptance,
preserving NOLOGIN/NOINHERIT/private schemas and independent denial tests.
No live build/grant/read, consumer endpoint or Q01 measurement has run in Phase5.
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
