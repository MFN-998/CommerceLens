# Phase 5 performance research — 2026-10-26

The first unfinished target at checkpoint `cd960c8` is the fixed unfiltered
executive overview. Its shared-projection diagnostic preserved all source fields
and results, but temporary traffic exceeded the original 512 MiB limit. The
subsequent scope-inlining experiment failed both the time and traffic limits.
Neither experiment was adopted.

## Primary sources and bounded inference

[PostgreSQL CTE documentation](https://www.postgresql.org/docs/17/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION)
explains that repeated references normally retain a CTE result, while a single
reference to a side-effect-free SELECT can be folded into its parent. Explicit
inlining can duplicate work. This supports inspecting repeated intermediate work;
it does not establish that a particular rewrite is faster.

[PostgreSQL resource documentation](https://www.postgresql.org/docs/17/runtime-config-resource.html#GUC-WORK-MEM)
explains that memory limits apply to individual sort/hash operations, and concurrent
sessions and workers can multiply their combined resource use. This experiment
keeps the approved memory limits rather than increasing them to mask spill.

[PostgreSQL EXPLAIN documentation](https://www.postgresql.org/docs/17/sql-explain.html)
describes actual execution measurement and temporary block statistics. Retained
EXPLAIN ANALYZE evidence, actual query results and independent rollback checks
remain required; an estimated plan is not performance acceptance.

These are versioned primary references, not a certification of the server's exact
patch release. No downloaded code, package, extension or service is needed.

## Current hypothesis and scope

In an overview without a state filter, scope and cohort contain the same rows.
Both customer counts use the same DISTINCT expression with literal C collation.
The reference count can therefore reuse the total's active-customer count,
including NULL exclusion and the zero count on an empty population.

The new diagnostic accepts only the exact original query, its fixed 2016–2019
parameters, no filters and original pagination. It removes the reference aggregate
and cross join, preserving the output alias and order. It does not use the rejected
scope-inlining hint. All other calculations and the full serialized response
fingerprint remain fixed. Grouped and filtered cases are rejected by this
experiment; their independent reference population remains unchanged in source.

This is an inference to test. One measured overview does not establish full Q01,
concurrency, consumer reconciliation, production adoption or Phase 5 completion.
The first variant retains the reader-local nested-loop experiment; the subsequent
normal-planner variant removes it and is recorded separately below.

## Dependency security boundary

No package or dependency change is proposed. For any later package proposal,
review official provenance, maintenance, compatibility, transitive dependencies,
known advisories, installation scripts and required privileges before installation;
use pinned versions and an isolated retained environment where practical. A clean
advisory scan cannot guarantee absence of vulnerabilities. Existing E11/E13/E14
findings remain open under their documented release gates; they are not resolved
by this performance experiment.

## Follow-up: estimate diagnosis before another mutation

The same query without the nested-loop override was cancelled during measurement.
Its retained estimated plan uses 249 filtered orders and 200 item groups, whereas
the prior executed plan observed 96478 and 98666 respectively. This is evidence of
poor estimates and a different join choice, not proof of each operation's runtime.

[PostgreSQL CREATE STATISTICS](https://www.postgresql.org/docs/17/sql-createstatistics.html)
documents per-expression statistics that can improve filter and grouping estimates
without maintaining an expression index. It also explicitly limits extended
statistics: they are not used for table-join selectivity. Creating an object alone
does not establish usefulness; collection, expression matching, privileges and the
actual resulting plan must be checked. The historical expression-index trial
records that ANALYZE was not run, so it does not answer this statistics question.

[PostgreSQL planner statistics security](https://www.postgresql.org/docs/17/planner-stats-security.html)
explains that statistics use can be constrained by privileges and operator safety,
including when reading security-barrier views. It also distinguishes generic
statistics that do not require evaluating stored values. These are hypotheses to
review against our exact expressions and roles, not reasons to widen reader grants
or mark functions LEAKPROOF.

Next inspect the retained subtree and prior index evidence, then determine the
smallest safe estimate/role diagnostic. No statistics collection, statistics object,
privilege change, extension or new package was introduced. Any future statistics
mutation requires reviewed rollback and independent restoration coverage beyond
the current view-catalog checks. No new statistics runner is prepared yet.
