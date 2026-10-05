# Phase 3 — Database, SQL & Analytics Engineering

Started 2026-09-20 from audited baseline `561b4b1` and execution-protocol checkpoint
`b06fe2e5e41d2a70aa15664ae078514cebca8628`. Branch: `feat/warehouse-foundation`.
Authority: [master plan](master-plan.md), [engineering standards](engineering-standards.md),
[execution protocol](execution-protocol.md), and root [work state](../WORK_STATE.md).

The owner created **CommerceLens** as the dedicated Supabase development project.
Project and PostgreSQL 17.6 connection verified on 2026-09-21; see the
[development warehouse guide](warehouse-development.md) for configuration and evidence.
The phase exit remains a **tested analytical warehouse**, not a deployed analytics app.

## Milestones and checkpoints

| Unit | Deliverable | Required exit evidence | State |
| --- | --- | --- | --- |
| M1. Warehouse contracts | ADR with schemas, grains/types, join/quality policies, role boundaries, and recovery contract | Phase 2 evidence reviewed; original decimal/ZIP fields inspected; design and source observations consistent | Design complete; implementation tracked in M2–M5 |
| M2. Isolated database foundation | Dedicated dev project; reviewed versioned bootstrap/migrations; secret-free examples and connection guidance | Target/version verified, encrypted connection, repeat migration, intended grants and denied access, API exposure review, disposable recovery test | Complete 2026-09-21: migration applied, replay/permissions/recovery checks passed |
| M3. Reproducible loading | All nine verified source tables, provenance/load registry, exact monetary ingestion, atomic load | Source/hash/count/content reconciliation, exact decimal checks, idempotent rerun, failed-load rollback, unchanged raw files | Complete 2026-09-22: all 1,550,922 rows committed; full content/count/money and repeat verification passed |
| M4. dbt staging and dimensions/facts | Pinned compatible dbt/Postgres tools; staging/intermediate/core models and explicit quality flags | dbt build, uniqueness/null/reference/domain tests, source reconciliation, synthetic grain and missing-data cases | Complete 2026-10-04: all nine source staging models verified (12/11/8/16/25/16/16/14/12 dbt tests); dim_location first/access/repeat verified (12 dbt tests); dim_seller first/access/repeat verified (11 dbt tests); dim_customer first/access/repeat verified (4 dbt tests); dim_product first/access/repeat verified (16 dbt tests); dim_date first/access/repeat verified (12 dbt tests); int_order_customers first/access/repeat verified (12 dbt tests); fact_orders first/access/repeat verified (33 dbt tests); fact_order_items first/access/repeat verified (19 dbt tests); fact_payments first/access/repeat verified (14 dbt tests); fact_reviews first/access/repeat verified (14 dbt tests) |
| M5. Initial marts and handoff | Order-grain technical mart and reliable example SQL; access/recovery/developer guidance | Independent child aggregation, conserved counts/sums, repeat build, query-plan review, reconstruction/recovery verification, final checks and checkpoint | Complete 2026-10-05: mart/reader/technical queries accepted; fresh reconstruction, full graph/rebuild, 42 independent native checks, private access/capacity and final handoff verified |

Each unit follows implement → validate → document → update WORK_STATE → commit → verify
Git status. Preserve the last known-good checkpoint before database, dependency, or
cross-cutting changes. A pending environment must not become a reason to invent passed tests.

## M1 decisions

See [ADR 0003](decisions/0003-warehouse-contract.md) and the
[aggregate source observations](warehouse-source-observations.json). In particular:

- Preserve source keys/ZIP strings. Every inspected customer/seller/geolocation ZIP was
  already five characters; leading zeroes occur in all three sources. No padding is needed.
- Load money from original decimal strings. All three monetary columns have at most
  two fractional digits. Use exact warehouse numeric types with validation before casting.
- Keep customers at cross-order identity separately from the order-linked customer record.
- Keep items, payments, and review facts at their actual child grains; aggregate independently.
- Create a unique ZIP domain with coverage/ambiguity metadata, without inventing a canonical
  geographic coordinate or collapsing changing customer addresses.
- Preserve and flag Phase 2 warnings; do not silently remove inconvenient rows or define KPIs.

## First database unit

The owner-created `CommerceLens` project is the verified development target in Tokyo.
Preserve its name and do not create a duplicate. The Free plan shows a 500 MB database
allowance: measure capacity before M3 loading or materializing dbt models. Confirm any paid commitment before submission. If creating or
changing a credential requires user entry, let the owner complete that step privately.
Never paste passwords/tokens into chat, WORK_STATE, tracked files, or logs.

Record only non-secret project/region/version/connection-method metadata after creation.
Use the project's actual Connect settings; do not invent a pooler hostname. Verify the
intended database and transport before applying reviewed bootstrap SQL. Keep warehouse
schemas out of Data API exposure and deny browser/anonymous access before loading records.

The phase cannot pass until a real database and dbt tests verify the implementation.
No database migration, load, schema test, connection test, or deployment has run in M1.

## Boundary

Initial marts and technical analytical queries are Phase 3 scope. Business EDA/findings
are Phase 4; official KPI definitions and the API-facing analytics layer are Phase 5.
Frontend integration/deployment and production automation remain in their master-plan
phases. This plan does not reopen or redo Phases 1–2.

M3 storage decision: retain Free and use views initially, per owner choice.
See [ADR 0004](decisions/0004-development-storage-budget.md) for limits and
[loading/recovery guide](warehouse-loading.md) for operational checks.

## M3 completed — 2026-09-22

All nine tables loaded using the restricted login. Complete replay verified the same
snapshot without duplication. Final raw/database sizes were 275,750,912 / 287,026,323
bytes, within approved ceilings; API access remains denied. Original source integrity
is unchanged. [Acceptance evidence](warehouse-load-verification.json) records counts,
content digests, exact monetary totals, attribution and storage. 
Next: [M4 dbt setup plan](dbt-setup-plan.md). Tooling and offline bootstrap are implemented
and verified. Restricted transformer provisioning/access and dbt debug passed on 2026-09-25;
All nine source staging models are verified, including geolocation first/access/repeat acceptance on 2026-10-03. All five dimensions, the order-customer mapping and all four core facts are accepted; M4 complete; M5 mart computation, scoped reader access, populated reconstruction and final native acceptance complete. See [Phase 3 completion](phase-3-status.md).
See [customer](customer-staging.md), [seller](seller-staging.md),
[category translation](category-translation-staging.md), [products](product-staging.md),
[orders](order-staging.md), [order items](item-staging.md), [payments](payment-staging.md),
[reviews](review-staging.md), [geolocation](geolocation-staging.md),
[location dimension](location-dimension.md), [seller dimension](seller-dimension.md)
[customer identity dimension](customer-dimension.md), [product dimension](product-dimension.md),
[date dimension](date-dimension.md), [order-linked customers](order-customers.md),
[order fact](fact-orders.md) and
[dbt development](dbt-development.md) guides.

## Required exit governance gate

After M1–M5 are complete and verified, perform the owner-required
[engineering and product-quality audit](deletion-and-governance.md). Fix Critical and
relevant Important issues, verify Phases 1–3 and document deferred debt before Phase 4.
This gate is pending; do not execute it during unfinished Phase 3 implementation.

## Phase 3 completion — 2026-10-05

M1–M5 and the master-plan exit, **tested analytical warehouse**, are COMPLETE.
The approved Free/Tokyo isolated target reproduced all nine source tables and
1,550,922 rows, with full-content/exact-money repeat verification and one unchanged
registry identity. Both full dependency builds passed all 20 views and 282 tests;
grant replay and compatible rebuild preserved mart identity/owner/options/ACL and
five default grants. All 42 independent cases across 22 files passed, with no
skips or errors. Final metadata confirms private access denials, unchanged source
provenance, views-only materialization and capacity within ADR 0004.

Final raw/database bytes: **275,988,480 / 287,135,411**.
See [completion handoff](phase-3-status.md) and
[final reconstruction receipt](warehouse-reconstruction-verification.json).
No Phase 3 implementation remains. The comprehensive governance audit is
**NOT YET RUN**; start it in a new CommerceLens chat and resolve its required
findings before a separate Phase 4 chat. Audit effort is not included in the
completed Phase 3 implementation estimate.

Technical queries and six dated plan samples retain Q01's latency/spill limitation.
Reconstruction is source/code reproducibility, not populated backup/PITR proof,
future reader-login authentication or production readiness. Business EDA remains
Phase 4; official KPIs/API analytics remain Phase 5. Preserve all established
grains, quality flags, exact-money policy and Free/views-first decisions.
