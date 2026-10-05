# Phase 4 — Exploratory and business analysis

Started 2026-10-05 in separate chat 01a10aac-b656-7982-ac89-a63faa542ee7.
M1–M3 COMPLETE / VERIFIED; M4 publication/transition is the containing checkpoint gate.
Final report: phase-4-eda-report.md; evidence: phase-4-eda-results.json and
phase-4-verification.json. Full offline suite 1669 passed, 1000 deliberate native
skips, known AnyIO warning. Two final runs match byte-for-byte and their receipts
match actual saved bytes; 17 aggregate partitions and historical totals reconcile.
Resume verified audit checkpoint 91afb0a and published transition bbe0455;
clean source tree, audit upstream equality, and account usage checked before edits.

## Atomic milestones

1. Establish reproducible exploratory contracts, hypotheses and safe runner.
2. Analyze all eight domains; reconcile populations and exact source money.
3. Validate associations and sensitivity, write findings and limitations, verify exit.
4. Publish verified checkpoint and prepare the separate Phase 5 handoff.

The runner reads the existing immutable CSV snapshot after checksum verification.
No acquisition, staging replacement, warehouse write, credentials or new dependency.
The accepted warehouse preserves source content; local analysis avoids repeated
views-heavy scans while Q01 remains an explicit Phase 5 workload gate.
Exploratory rules do not establish official KPI policy or API contracts.

## Hypotheses before analysis

- H1: The middle purchase months show growth, with incomplete boundary months.
- H2: A small category/product set accounts for a large share of item value.
- H3: Cross-order customer identity has low observed repeat ordering.
- H4: Seller item value is concentrated; operational comparisons need minimum support.
- H5: Cross-state fulfillment is associated with longer delivery duration.
- H6: Credit-card components dominate observed payment value and installments vary.
- H7: Late delivery is associated with more low review scores.
- H8: Freight burden and category mix identify operational investigation priorities.

Each result must state grain, eligibility, numerator/denominator and uncertainty.
Use all statuses for source descriptions and delivered subsets as sensitivity.
Keep exact money from CSV decimal text, naive clocks, all review pairs, missing
families and geographic ambiguity. Use no selected review or canonical coordinate.
Durations require present, ordered event pairs. Compare timestamp lateness with
calendar-date lateness; neither becomes official policy. Seller/category order
counts can overlap; order outcomes cannot establish responsibility for an item.
No profit, causal effects, live-2026 extrapolation or retention/cohort product.

## Exit evidence

Structured report and aggregate-only machine-readable evidence, deterministic
replay, meaningful synthetic failure/grain/time/money tests and source checks.
Review diff, staged content, secret scans and publication state. Carry Q01,
E01–E10, source-version, coordinates, auth/exposure/backup/release gates forward.
Retain all generated evidence and resources under the permanent deletion rule.
