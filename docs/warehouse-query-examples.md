# Technical query examples and measurements

Phase 3 M5. VERIFIED: source, native results and bounded development measurements.
Continues accepted mart/reader checkpoint 7b3cc8c. No model or data rebuild is required.

## Purpose and contracts

The three versioned SELECTs in [warehouse/queries](../warehouse/queries/README.md)
demonstrate total, observed-month and bound-period/status aggregation of the accepted
one-order mart. Each exposes the same 33 source aggregates, with a grouping field
when relevant. They return no order/customer identifiers, addresses or review text.
No new joins, status eligibility, selected review, official revenue/GMV, EDA finding,
dashboard or API is introduced. Warning counts can overlap and are not summed into
a distinct count of problematic orders.

Count aggregates are zero for empty totals; source amounts stay NULL when no
measured amount exists. Grouped queries return no synthetic rows for an empty
population, retain an unknown-month/status group if present, and fill no calendar gaps.
Required-source validation still applies; these synthetic edge cases do not excuse
invalid upstream source data. Exact native numeric amounts remain unconstrained.

Period dates use psycopg bindings, not SQL interpolation. Bounds are inclusive start
midnight and exclusive end midnight against the unchanged timezone-naive source
timestamp. Monthly grouping invents no timezone, current date or business eligibility.
Literal C status grouping preserves case/space distinctions.

## Verification and safe measurement

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:COMMERCE_WAREHOUSE_QUERY_EXAMPLES_INTEGRATION='1'
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_query_examples_postgres_integration.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -B -m scripts.measure_warehouse_queries --run
```

Native fixture checks bind tiny typed CTE inputs to the actual SQL and compare all
outputs with an independent Python Decimal/group oracle. They use the restricted
transformer login without activating any warehouse role or reading real source rows.
The measurement tool uses existing private admin configuration only to assume the
NOLOGIN reader inside a repeatable-read, read-only transaction with verify-full TLS,
55-second statement and five-second lock timeouts. This is development capability
verification, not future reader-login authentication or production API behavior.

Only three fixed reviewed SELECTs execute, serially: one result read and two
EXPLAIN ANALYZE measurements each. The example period is 2018-01-01 through
2018-02-01. All-time source totals must match the accepted immutable snapshot;
observed months must conserve all 33 aggregates and the period/status partition
must reconcile to January's monthly row. A fresh connection verifies mart identity,
owner, ACL/default privileges and the existing 400M storage ceiling afterward.

Full plans and progress receipts remain ignored under a unique
.artifacts/warehouse-queries directory; no cleanup or overwriting older runs occurs.
Published summaries omit conditions/output/source values. Buffers are reported
from the root because parent counters already include child work. Node timing is
disabled to reduce instrumentation overhead; total execution time remains measured.
See [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/17/sql-explain.html) and
[read-only transactions](https://www.postgresql.org/docs/17/sql-set-transaction.html).

On failure/interruption preserve and inspect the retained receipt/plans. Failure
before acceptance normally leaves complete:false; a final file write can be partial
or acceptance can already be saved before the command return is interrupted. Do
not infer acceptance from the command outcome alone. No model rebuild, grant change
or source reload is needed; inspect the first unverified gate before retrying.
Raw driver details are suppressed.

## Interpretation and remaining work

These serial development samples are not cold-cache measurements, concurrency tests,
production latency guarantees or an SLO. EXPLAIN measures execution/instrumentation;
client timings also include network and driver work. `hash_disk_kb` sums exposed
Disk Usage fields, typically HashAggregate; a batched Hash node can spill without
that field. Check max_hash_batches and root temp counters even when it is zero. Two repetitions characterize
this run only; they do not establish a percentile distribution.

The accepted [aggregate receipt](warehouse-query-verification.json) records the
retained run and all six plan summaries. Source totals and both partitions reconciled;
mart identity/owner/ACL/defaults and database size 287,345,811 bytes were unchanged.
Admin and transformer passwords were absent from all retained measurement outputs.

| Query | Result rows | First result read, client seconds | Server execution, two samples (seconds) |
| --- | ---: | ---: | ---: |
| Total components | 1 | 11.158 | 8.645 / 8.192 |
| Observed purchase months | 25 | 7.045 | 7.030 / 6.994 |
| Bound January 2018 statuses | 6 | 4.809 | 3.985 / 3.972 |

**Q01 — Important before API-facing analytics.** These full 33-aggregate examples
pass the bounded development timeout; this does not establish interactive readiness.
All six plans recorded 20,533 shared-buffer hits and no shared reads, but temporary
traffic remained: 12,627-18,472 blocks read and 13,853-19,699 written. Each had eleven
leader/worker disk-sort instances totaling 70,144-70,160 KiB of reported sort space,
hash aggregation up to 21 batches and 11,968-11,984 KiB exposed hash disk usage.
Those are summed operator statistics, not peak simultaneous disk usage. Block size
was not measured here, so temp counters are not converted to bytes.

The period query retains 7,269 qualifying orders but still builds roughly 98-99
thousand child groups. Estimates are materially inaccurate: child groups often
estimate 200, and one merge join estimates about 16.38 billion versus 56,325 actual
rows per loop over two loops. These are estimate errors, not observed child fanout;
the grain and component reconciliation checks passed. One worker was planned but
none launched on a branch; its cause is unverified. TIMING OFF prevents assigning
exact elapsed seconds to individual operators.

Retain Free/views-first ADR 0004. Before Phase 5 API use, measure actual projections,
filters, concurrency and response budgets, then review statistics/indexes or
materialization/caching only when evidence and storage/rebuild capacity justify it.
No performance-related schema, configuration or dependency change was made here.
This scoped finding is not the comprehensive post-Phase 3 governance audit.
Full populated reconstruction and final handoff remain M5. The comprehensive
governance audit follows verified Phase 3 completion, before Phase 4.

Source verification: 11 focused offline cases passed; warehouse/API regression
1,394 passed / 1,000 deliberate live skips. Ruff lint/format154 files, mypy23
implementations plus the measurement script passed. Optional-fetch/import issues
were corrected before checkpoint. Eleven native PostgreSQL cases passed in 18.05s; all three SQL files/all 33 fields,
empty/NULL/zero/warnings, literal groups, period boundaries, leap dates, UTC/Honolulu
and large exact-numeric headroom matched an independent oracle. Physical reader
measurements and scoped full-plan summary review passed; populated reconstruction
has not yet run.
