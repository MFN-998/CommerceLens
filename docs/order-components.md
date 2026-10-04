# Order-component mart milestone

Phase 3 M5, 2026-10-04. Continues completed M4 checkpoint 1b67dc5.
Status: COMPUTATION VERIFIED. M5 access/examples/performance/recovery remain.

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

This unit's computation acceptance is complete. Next apply scoped reader access,
write reliable technical query examples, measure
query plans/performance, prove reconstruction/recovery, and complete phase handoff.
The comprehensive governance audit runs after verified Phase 3, before Phase 4.
Full source/frontend/advisory checks remain historical 2026-09-22 for unchanged inputs;
E2E, deployment and the comprehensive audit have not run.

## Accepted computation evidence

85 candidate offline, 171 adopted mart/runner, 1,370 retained warehouse/API
(983 deliberate live skips), 71 native read-only PostgreSQL and two physical
read-only tests passed. Ruff lint/format (144 files), mypy (22 implementation
files) and offline parse passed. Initial test import-spacing issue corrected;
final lint passed. Known AnyIO alias warning only, no unresolved mart failures.

First/repeat each passed one view/all five dbt tests in
71.852/66.875s. All 99,441
orders and 33 unchanged parent fields/lineages conserved, plus every order's
components. Retained 112,650 items, 103,886 payments, 99,224 review pairs and
547 multiple-review orders. Exact source price/freight/payment sums:
13591643.70 / 2251909.54 / 16008872.12.
Orders without items/payments/reviews: 775 /
1 / 768. Those
orders remain, absent sums NULL and counts zero. Warning totals remain 0/4 item,
2/9/3 payment and zero reversed-review events. These are technical source totals.

Independent raw/core/mart aggregate and complete parent/per-order component
checks passed, along with native types/typmods/collations/owner, private restricted
session/TLS and current API/public/reader denials. Repeat preserved identity/owner/
grants; password absent from both artifacts. Database 287,337,619 bytes
below the 400M ceiling. Suite timings are not consumer-query latency. Source
dc81385 published before live build; [aggregate evidence](order-components-verification.json)
records node statuses and retained paths. No resource deletion or upstream redo.

Reader SELECT is intentionally still denied pending the next scoped grant unit;
positive reader access, reliable examples, consumer plans/performance and full
reconstruction/recovery are not yet verified. Phase 3 is incomplete and the
required post-Phase 3 governance audit has not begun.
