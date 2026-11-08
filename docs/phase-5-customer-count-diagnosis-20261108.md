# Distinct-customer count diagnosis — 2026-11-08

The accepted four-view probe preserved every source contract and the complete
response, but its single overview sample took 10292.353 ms against the unchanged
10000 ms limit. Temporary traffic was 519340032 bytes against 536870912.

## Retained evidence

Artifact: `.artifacts/phase-5/d4a3e6eb59f14e3097e0f98d57d4f302`.
The execution plan hash matches the published verification record. Node
`0.1.0.0.0.0` sorts 96478 scope rows for the distinct-customer aggregate with
estimated width 295 bytes and external-merge disk space 18440 KiB. Its reported
temporary traffic exceeds its direct child's by 9222 blocks (75546624 bytes).
These node counters overlap elsewhere; they must not be summed into a new total.
TIMING OFF means this evidence does not attribute elapsed time to that node.

The scope still estimates 53983496 rows versus 96478 actual. Payment and review
aggregates estimate 200 groups versus 99440 and 98673 actual. Those are separate
remaining estimate problems; this experiment does not change those models.

## One bounded experiment

Only for the already-bound unfiltered overview, change the totals expression:

```sql
count(distinct customer_unique_id collate "C") as active_customers
```

to:

```sql
(select count(distinct customer_unique_id collate "C") from scope) as active_customers
```

The extra scan reads the same materialized scope. This may let PostgreSQL sort
only the customer identity instead of wide totals rows. That is a hypothesis to
measure, not an assumed improvement. Keep active/reference count reuse, exact
column order/types, NULL exclusion, literal C collation and empty-scope zero.
The rewrite rejects all different SQL, parameters, grouped or filtered queries.

PostgreSQL documents that distinct counts ignore NULLs and count distinct
non-NULL inputs ([aggregate expressions](https://www.postgresql.org/docs/17/sql-expressions.html#SYNTAX-AGGREGATES)).
An uncorrelated single-row subquery may become a once-per-query InitPlan
([EXPLAIN](https://www.postgresql.org/docs/17/using-explain.html)). The planner can
provide presorted input for DISTINCT aggregates
([query planning](https://www.postgresql.org/docs/17/runtime-config-query.html#GUC-ENABLE-PRESORTED-AGGREGATE)).
These support the semantics and mechanism, not a promised speedup.

Five native synthetic cases cover empty input, NULL-only identities, duplicates,
case/trailing-space/empty-string distinctions and Unicode distinctions. All four
full-source comparisons, the complete response hash, exact catalog checks, client
TLS, normal planner, original time/space budgets and fresh-process independent
restoration remain required. No package, persistent adoption or production query
change is included. Full Q01 and consumer reconciliation remain separate gates.
