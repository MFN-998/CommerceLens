# Read-only estimate diagnosis — 2026-10-28

## Follow-up: controlled boundary reproduced

The [fixed paired comparison](phase-5-cte-boundary-pair-verification.json) now
reproduces the estimate loss: plain derived SELECT87208 groups, WITH-containing
subquery200 groups. Both use identical normalized IDs, C collation, transformer
role, snapshot and settings. Both raw scans estimate112650 rows and both top
aggregates are simple hashed aggregates. Only the WITH version retains a Subquery
Scan. Independent restoration passed, with unchanged database/raw sizes.

This justifies testing a CTE-free item staging projection. It is not executed
latency evidence or full model equivalence. Preserve parsing and independent
reconciliation before adopting any model rewrite.

The broader search included GitHub, Stack Overflow and developer discussions.
The directly relevant primary references remain the PostgreSQL17 source and
developer proposal linked below. The [official patch tracker](https://commitfest.postgresql.org/patch/7283/)
currently lists a proposed PostgreSQL20 change needing review; it is not an
available fix for this PostgreSQL17 recovery database. No patch, package,
extension or upgrade was installed. Proposed third-party packages would require
provenance, maintenance, advisory, dependency, install-script and permission
review before installation; none is needed for this SQL comparison.

## Earlier 15-plan diagnosis

All 15 fixed EXPLAIN-only cases completed against unchanged deployed views.
Independent catalog/access/settings restoration and all 99 source bindings passed;
database287594163 bytes and raw275988480 bytes were unchanged during the job.
The server reports170011. No package, statistics object, ANALYZE, grant, planner
setting or production source change was introduced.

## What the evidence isolates

The transformer sees four selected raw-column statistics; the reader sees none.
All four identical mart query plan summaries nevertheless match across those roles.
This does not support reader permissions as the explanation for these differences.
Empty reader pg_stats results describe visibility, not global absence.
[PostgreSQL pg_stats](https://www.postgresql.org/docs/17/view-pg-stats.html) describes
its access filtering. Existing raw statistics also mean zero/resettable activity
counters cannot establish that analysis never occurred.

Raw item-ID grouping estimates87208 groups. Applying NULLIF directly still gives
87208; grouping through staging or the item mart gives200. The staging plan retains
a Subquery Scan. Both relevant staging views have null reloptions, so this is not
evidence of a configured security_barrier view. No security setting was changed.
The status and parsed-date expressions also reduce selectivity estimates; parallel
scan estimates in the receipt are node/worker estimates, not actual global counts.

## Primary-source finding and next controlled test

The [PostgreSQL17 stable-branch planner source](https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/src/backend/optimizer/prep/prepjointree.c)
checks for a nonempty WITH list in is_simple_subquery and declines pull-up.
That can retain a subquery boundary even when a CTE is otherwise inlineable.
This is a plausible explanation for the observed staging boundary, not a proven
runtime cause or a recommendation to change every CTE.

A [September2026 PostgreSQL developer proposal](https://www.postgresql.org/message-id/15507998da7eff34854a5de3494fe9d8@postgrespro.ru)
addresses this restriction. It is a proposed patch, not evidence of an installed
fix, an approved upgrade or a package to download. No patch was downloaded/executed.

Next prepare two fixed read-only EXPLAIN queries with identical normalized item-ID
expressions and C collation: one ordinary derived SELECT and one WITH-containing
subquery. Use the same transformer role and existing settings/deadlines. This tests
the CTE boundary without DDL. If it changes estimates, review a CTE-free projection
of stg_order_items before implementing any source change. Preserve every source
column/type, NULL/invalid parsing behavior, lineage and independent reconciliation.
The full source equality/performance gates would apply to an actual candidate.

Expression statistics remain a later feasibility option. PostgreSQL documents
[their benefits and join-estimation limitations](https://www.postgresql.org/docs/17/sql-createstatistics.html).
They are not needed to run the next controlled comparison. Full Q01, concurrency,
consumer reconciliation and Phase5 completion remain open.
