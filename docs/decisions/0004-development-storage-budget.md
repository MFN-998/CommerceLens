# ADR 0004: Free-plan storage and initial view materialization

Accepted 2026-09-21 after measured sampling and the owner's explicit choice to keep Free.
This refines physical materialization within Phase 3; all logical models and source rows remain.

## Evidence and decision

The [storage estimate](../warehouse-storage-estimate.json) sampled up to 10,000 records
per source using a deterministic reservoir and the actual PostgreSQL text landing layout:
UUID load identity, bigint logical ordinal, and a composite primary key. Source bytes
were verified before/after; temporary tables were rolled back. Estimated raw storage,
including indexes/TOAST, is **293,382,593 bytes**. A 25% margin gives **366,728,242 bytes**.

The initial budget reserved 40 MB for platform/baseline growth, 75 MB for materialized
models, and 50 MB for build work: **531,728,242 bytes**, exceeding the conservative decimal
500,000,000-byte allowance. This initial gate failed and is retained in the evidence.

The owner selected views initially, with a fresh storage review before materialization.
Reserve 10 MB for initial model definitions/small metadata instead of 75 MB for copies.
The revised budget is **466,728,242 bytes**, leaving **33,271,758 bytes** unallocated.
There is no paid upgrade, omitted source table, sampled final dataset, or altered KPI scope.

## Enforcement and consequences

- One verified source snapshot per development target. Another version requires a new
  capacity/retention review; the loader must not append it automatically.
- Loader checks the current database before loading and actual raw/database sizes before
  commit. Raw ceiling: 367,000,000 bytes; database ceiling: 400,000,000 bytes to preserve
  later build/model headroom. Exceeding a ceiling rolls back; never truncate source rows.
- M4 starts with views for staging/core/marts. Logical dimensions/facts, keys, tests, and
  separation of concerns still apply. Materialize only after measuring storage, rebuild
  overlap, query performance, and the remaining allowance. Views can trade storage for CPU.
- Estimates are not guarantees. Small-sample extrapolation, page fill, runtime database
  growth, and platform billing can differ. Reconcile actual size after loading.
- WAL and filesystem temporary space have their own operational impact; a database-size
  estimate is not proof of unlimited disk or transaction headroom.

## Reproduction

Use immutable source version 2 and the row counts/hashes in the evidence. For each table,
reservoir-sample at most 10,000 logical CSV records with Python `random.Random` seeded by
`CommerceLens storage v1 ` plus the table's contract name; preserve original row ordinals.
Create temporary all-text tables with the approved metadata/primary key, COPY sampled
rows in source order, then measure `pg_total_relation_size` and scale by full/sample rows.
Sum estimates, apply the recorded margin/reserves, and roll back all temporary objects.
See [PostgreSQL size functions](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADMIN-DBSIZE)
and [Supabase size metrics](https://supabase.com/docs/guides/platform/database-size).
