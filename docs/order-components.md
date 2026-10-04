# Order-component mart milestone

Phase 3 M5, 2026-10-04. Continues completed M4 checkpoint 1b67dc5.
Status: SOURCE VALIDATED; first live build, physical and repeat acceptance pending.

## Contract

Private marts.mart_order_components view: one literal order_id, all 33 unchanged
fact_orders fields and 16 technical child fields. Aggregate items, payments and
reviews independently before literal C-collated LEFT JOINs to every order.
Counts are source row counts, including all split payments and review/order pairs.
Each warning count retains its accepted source flag. No canonical review is selected.

Absent children have count zero and false presence. Source price, freight and payment
sums remain NULL when their family is absent; real measured zero remains numeric zero.
SUM(numeric) returns exact unconstrained numeric, avoiding a numeric(18,2) aggregate
overflow when several valid maximum components are combined. No float, rounding,
imputation, item/payment equality, status eligibility, duration, GMV or revenue policy.
See [PostgreSQL aggregate semantics](https://www.postgresql.org/docs/17/functions-aggregate.html).
Phase 4 EDA and Phase 5 business definitions retain their master-plan boundaries.

## Verification and operation

One configured order_id not-null test and four singular tests check literal grain,
derived domains/presence/missingness/warning bounds, all 33 parent fields as a complete
multiset, and each order's child components. The independent child oracle unions
families into long form before grouping rather than repeating the model's joins;
it catches redistribution that globally conserved totals would hide.
Upstream accepted models retain their own detailed source/domain/reference gates.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select mart_order_components
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select mart_order_components
```

Use [retained warehouse checks](customer-staging.md) and dedicated transformer settings.
Enable COMMERCE_WAREHOUSE_ORDER_COMPONENTS_INTEGRATION=1 only for the intended read-only
native/physical modules. All outputs remain ignored and retained. The custom view
materialization preserves compatible relation identity/ownership/grants and commits
before acceptance tests; a failed test is not rollback. Preserve artifacts and diagnose
without a source reload, full refresh, DROP or unapproved resource deletion.

Views-first/Free [ADR 0004](decisions/0004-development-storage-budget.md) still applies.
No schema migration, dependency, credential, API/UI or materialization change is needed.
Reader currently has schema usage only; an explicit approved-mart SELECT grant and
positive/negative read verification remain a separate M5 access step. No blanket
default grants or browser/Data API exposure are authorized.

## Remaining M5 work

Finish this unit's offline/native/first/physical/repeat verification and checkpoint.
Then approve scoped reader access, write reliable technical query examples, measure
query plans/performance, prove reconstruction/recovery, and complete phase handoff.
The comprehensive governance audit runs after verified Phase 3, before Phase 4.
Full source/frontend/advisory checks remain historical 2026-09-22 for unchanged inputs;
E2E, deployment and the comprehensive audit have not run.

Source validation: 85 candidate offline tests, 171 adopted mart/runner tests,
1370 retained warehouse/API tests (983 deliberate live opt-out skips)
and 71 native read-only PostgreSQL tests passed. Ruff lint/format and mypy
22 implementation files passed. Offline parse passed: .artifacts/dbt/f69941d5631743bc93b5fc6c3f6dbdb8.
Preflight: four accepted facts/counts/exact sums/warnings unchanged; mart absent;
database 287,288,467 bytes. Source checkpoint precedes live view construction.
Physical/repeat verification has not run. Detailed older M4 evidence stays in
each fact/dimension guide and verification JSON; it is not rerun unnecessarily.
