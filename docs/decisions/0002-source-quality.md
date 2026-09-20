# ADR 0002: Versioned source acquisition and faithful local staging

Status: Accepted for Phase 2, 2026-09-19.
Follow-up: the [2026-09-20 engineering audit](../engineering-audit-phase-1-2.md) hardens
numeric/CSV handling, failure-report privacy, and single-writer validation without changing
the verified Olist snapshot or source grains.
Authority: [Master plan](../master-plan.md), Phase 2.

## Context

Olist contains tables at different grains and known missing or inconsistent events.
Reliable downstream analysis first needs reproducible source data and explicit quality
evidence. A successful parse alone does not establish that a join or metric is valid.

## Decisions and reasons

1. Acquire official Olist version 2 with KaggleHub. Commit source/license metadata and
   per-file hashes, while keeping all full datasets outside Git. Pinning a release and
   verifying bytes makes a future run comparable to this one.
2. Keep raw bytes immutable. Local Parquet staging preserves all rows and source names,
   with explicit types and `_source_row` provenance. Raw acquisition is guarded by a
   lock and prepares files before publication; staging publishes a complete directory
   only after validation and Parquet round-trip checks.
3. Separate data dependencies from API runtime dependencies. pandas provides profiling,
   Pandera provides executable contracts, and PyArrow provides typed file storage. This
   is the master plan's local data foundation; PostgreSQL and dbt remain Phase 3 work.
4. Block missing files/columns, malformed records, parse failures, invalid confirmed
   keys, impossible required values, and mandatory-reference orphans. Preserve contextual
   warnings for review. `PASS_WITH_WARNINGS` certifies a faithful staged source with
   disclosed limitations, not universal fitness for business analysis.
5. Preserve optional missing text and event times, multiple reviews, repeated geography
   rows, literal `NA`, and original string identifiers. Do not invent imputation,
   deduplication, timestamp corrections, or ZIP normalization during acquisition.
6. Keep source timestamps timezone-naive: a timezone was not declared by the source.
   Numeric measures use nullable numeric types for profiling. Floating-point money in
   this snapshot does not define an accounting precision policy. Phase 3 must choose
   exact warehouse numeric types from raw decimal values before monetary aggregation.

## Observed grains and relationships

| Source table | Enforced grain/key | Relationship or handoff constraint |
| --- | --- | --- |
| customers | One source customer/order identity per `customer_id` | `customer_unique_id` repeats across orders; use it for later cross-order customer identity |
| orders | One order per `order_id` | `customer_id` must reference customers |
| order_items | One item sequence per `(order_id, order_item_id)` | Must reference orders, products, and sellers |
| order_payments | One payment component per `(order_id, payment_sequential)` | Must reference orders; multiple components per order are valid |
| order_reviews | One observed review/order pair per `(review_id, order_id)` | Must reference orders; neither individual ID is unique in this release |
| products | One product per `product_id` | Category translation can be missing; flagged as a warning |
| sellers | One seller per `seller_id` | Source ZIP may be missing from geography; flagged as a warning |
| category_translation | One English mapping per source category name | 71 mappings; does not cover every product category |
| geolocation | One source record; no natural unique key | ZIP prefixes and full records repeat; `_source_row` identifies retained records |

Both customer and seller ZIP prefixes reference a nonunique geography domain. Reference
coverage is checked, but a many-row geography join is not endorsed. Define and test a
unique mapping in Phase 3 before use. Items, payments, and reviews also have independent
child grains. Aggregate them separately to the intended grain before joining; the quality
report quantifies item/payment row multiplication without defining a business KPI.

## Consequences and limits

The pipeline can reproduce and diagnose source limitations without concealing them.
Downstream eligibility rules still need decisions: which order statuses to include,
how to handle impossible event sequences, missing dimensions, multiple reviews, and
geographic ambiguity. These decisions must be documented and tested in the appropriate
later phase, not silently embedded in raw ingestion.

The rough Brazil coordinate box and one-year shipping-deadline check are exploratory
warnings, not authoritative geographic or business constraints. Nullability is explicit
per column; permitted nulls are still measured. Diagnostic counts can overlap and must
not be added to claim a number of distinct bad records.

Snapshots are immutable and intentionally single-version for this phase. Changing the
source release, staging contract, or serialization toolchain may require a reviewed
new snapshot/version; the pipeline refuses to overwrite different output. Reproducibility
was checked on the pinned Windows environment, not every platform or future library version.

See [data setup](../../data/README.md), [quality report](../data-quality-report.md), and
[the dictionary](../data_dictionary/initial.md) for commands and observed evidence.
