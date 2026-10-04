# Technical query examples and measurements

Phase 3 M5. SOURCE VERIFIED; native result verification and measurements pending.
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

On failure/interruption preserve the partial receipt/plans; its complete flag stays
false. No model rebuild, grant change or source reload is needed for measurement.
Investigate the first failed gate before retrying. Raw driver details are suppressed.

## Interpretation and remaining work

These serial development samples are not cold-cache measurements, concurrency tests,
production latency guarantees or an SLO. EXPLAIN measures execution/instrumentation;
client timings also include network and driver work. `hash_disk_kb` sums exposed
Disk Usage fields, typically HashAggregate; a batched Hash node can spill without
that field. Check max_hash_batches and root temp counters even when it is zero. Two repetitions characterize
this run only; they do not establish a percentile distribution.

Views trade storage for computation. Inspect actual scan/sort/hash/spill evidence
before considering indexes/materialization; keep the existing Free/views-first policy
and no premature performance changes. Measured results and acceptance are pending.
Full populated reconstruction and final handoff remain M5. The comprehensive
governance audit follows verified Phase 3 completion, before Phase 4.

Source verification: 11 focused offline cases passed; warehouse/API regression
1,394 passed / 1,000 deliberate live skips. Ruff lint/format154 files, mypy23
implementations plus the measurement script passed. Optional-fetch/import issues
were corrected before checkpoint. Actual PostgreSQL query/results/plans not yet run.
