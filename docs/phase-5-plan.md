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

M1 policy is in kpi-dictionary.md. Implementation and Q01 acceptance are pending.
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
