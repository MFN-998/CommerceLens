# Phase 2 — Data Acquisition, Profiling & Quality

Status: Completed on 2026-09-19, after Phase 1 completion was confirmed.
Evidence: [Phase 2 completion record](phase-2-status.md).
Authority: [Canonical master plan](master-plan.md), especially sections 6, 8, 10, 29–31, and 36.
Working directory: `D:\My Projects\CommerceLens`.
Branch: `feat/data-ingestion`.

## Objective and exit condition

Acquire the official Olist dataset, preserve its raw bytes, determine source grains and
relationships, and produce reproducible local staging data with documented quality.
Success means a developer can repeat acquisition, profiling, staging, and validation and
understand any unresolved source limitations. It does not mean every source row is perfect.

## Sequence

| Step | Work | Evidence |
| --- | --- | --- |
| 1. Source acquisition | Confirm official source/version/license; obtain the nine CSVs; record hashes and byte sizes | Tracked source manifest and data README; ignored raw snapshot |
| 2. Inventory and grains | Inspect columns, row counts, key candidates, duplicates, and child/parent multiplicity | Machine-readable inventory and initial data dictionary |
| 3. Profiling | Measure missingness, value ranges, categories, parse failures, relationships, and timestamp anomalies | Observed counts with explicit severity and interpretation |
| 4. Staging and validation | Apply explicit nullable types, preserve identifiers/rows, validate schemas and confirmed invariants | Local Parquet staging outputs, schema checks, automated tests |
| 5. Review and handoff | Record decisions, quality limitations, rerun evidence, and future join constraints | Quality report, Phase 2 status, clean Git commit |

## Decisions

- **Official versioned source:** use `olistbr/brazilian-ecommerce` on Kaggle and pin the
  acquired version. Record the license as source metadata; do not invent a code license.
- **Immutable raw snapshot:** repeated acquisition verifies hashes. A differing raw file
  is an error, not a reason to overwrite it. Raw and staging datasets stay out of Git.
- **Local staging:** this phase standardizes files locally. PostgreSQL and dbt begin in
  Phase 3. Parquet preserves explicit numeric, string, and timestamp types for that handoff.
- **Identifiers are strings:** customer/order/product/seller identifiers and ZIP prefixes
  are not quantities. Keep leading zeros and preserve source spelling and case.
- **No silent cleaning:** preserve all source rows, optional missing values, multiple
  reviews, and repeated geography records. Parse failures are counted and block promotion.
  Do not impute values, deduplicate by assumption, or trim valid free-text fields.
- **Validate before promotion:** schema/parse/key/reference failures stop a new staging
  snapshot. Warnings remain visible in a `PASS_WITH_WARNINGS` report.
- **Keep dependencies scoped:** pandas, Pandera, PyArrow, and KaggleHub belong in an
  explicit data dependency group. The Phase 1 API still installs without them.
- **Reproducible commands:** scripts replace hidden notebook state. Tests use small,
  synthetic fixtures and do not require the full dataset or a network connection.

## Quality policy

Blocking errors include missing source files/columns, invalid required identifiers,
unparseable typed values, invalid confirmed keys, negative money, and orphan mandatory
references. Contextual warnings include lifecycle inconsistencies, absent optional
relationships, incomplete product attributes/translations, duplicate geography rows,
and multiple reviews. Establish the rule from evidence; do not reinterpret a warning
as a clean bill of health.

Review missing event dates by order status. Optional review text is different from a
missing order identifier. A parent with no child row is different from a child whose
parent is missing. Payment/item totals may be compared as a diagnostic, but a business
reconciliation rule requires investigation rather than automatic data rewriting.

## Acceptance checklist

- [x] Source/version/license and historical-data limitation documented.
- [x] Raw snapshot verified by hashes; existing differing files cannot be overwritten.
- [x] All source files inventoried with rows, columns, sizes, and checksums.
- [x] Each table's grain and candidate keys documented using actual observations.
- [x] Missingness, duplicates, relationships, types, ranges, and lifecycle anomalies profiled.
- [x] Initial column dictionary records staging types and observed nullability.
- [x] Staging retains raw row counts and identifiers, with explicit source-row provenance.
- [x] Schema checks and failure-path tests pass.
- [x] Human-readable and machine-readable quality reports agree and disclose warnings.
- [x] Repeated processing verifies raw integrity and equivalent staging content.
- [x] Changes reviewed and committed with Phase 2 completion status accurately recorded.

## Boundaries

No PostgreSQL/Supabase provisioning, dbt models, dimensional tables, marts, business EDA,
KPI implementations, dashboards, ML, or deployment in this phase. Completing this
checklist does not start Phase 3 automatically.
