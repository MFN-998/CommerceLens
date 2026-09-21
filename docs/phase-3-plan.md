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
| M1. Warehouse contracts | ADR with schemas, grains/types, join/quality policies, role boundaries, and recovery contract | Phase 2 evidence reviewed; original decimal/ZIP fields inspected; design and source observations consistent | Complete; implementation still pending |
| M2. Isolated database foundation | Dedicated dev project; reviewed versioned bootstrap/migrations; secret-free examples and connection guidance | Target/version verified, encrypted connection, repeat migration, intended grants and denied access, API exposure review, disposable recovery test | Complete 2026-09-21: migration applied, replay/permissions/recovery checks passed |
| M3. Reproducible loading | All nine verified source tables, provenance/load registry, exact monetary ingestion, atomic load | Source/hash/count/content reconciliation, exact decimal checks, idempotent rerun, failed-load rollback, unchanged raw files | Partial: capacity/source contracts complete; landing migration tested; full load pending |
| M4. dbt staging and dimensions/facts | Pinned compatible dbt/Postgres tools; staging/intermediate/core models and explicit quality flags | dbt build, uniqueness/null/reference/domain tests, source reconciliation, synthetic grain and missing-data cases | Not started |
| M5. Initial marts and handoff | Order-grain technical mart and reliable example SQL; access/recovery/developer guidance | Independent child aggregation, conserved counts/sums, repeat build, query-plan review, reconstruction/recovery verification, final checks and checkpoint | Not started |

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
See [ADR 0004](decisions/0004-development-storage-budget.md) and
[aggregate load plan](warehouse-load-plan.json). Source landing preserves all rows;
actual restricted credentials, complete COPY, retry, and corruption checks remain pending.
