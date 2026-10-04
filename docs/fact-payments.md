# Payment fact milestone

Phase 3 M4, 2026-10-04. Continues accepted item-fact checkpoint 0171b40.
Private core view; no dependency, migration or source reload.

## Contract and decisions

One retained component at (order_id, payment_sequential), including all ten
accepted payment-staging fields. Source IDs/methods retain literal spelling;
numeric(18,2) amounts never pass through floats. Preserve immutable _load_id and
_source_row, source installment counts and all three zero/undefined warning flags.
An order can have several methods/components; no selected component, summation,
deduplication, filtering, repair or analytical eligibility is introduced here.

This core projection deliberately has no joins. Required literal membership in
fact_orders is tested separately, avoiding fanout if a parent becomes invalid.
Missing/rejected mandatory input remains visible and blocks acceptance. Warning
flags can overlap and do not determine eligibility. Payment and item/freight totals
are separate technical source reconciliation values; no equality is asserted.
The later technical mart aggregates each child independently before joining orders.

## Validation and operation

Ten required-field dbt checks and four singular checks cover composite grain,
domains/flag correspondence, complete bidirectional row-multiset conservation and
required order membership. Synthetic offline/native checks exercise real SQL and
configured null macros. Physical acceptance independently compares raw/staging/core
attributes, lineage, exact money and flags, native types and private access.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select fact_payments
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_payments
```

Use [customer staging](customer-staging.md) for retained regression commands.
COMMERCE_WAREHOUSE_FACT_PAYMENTS_INTEGRATION=1 opts in only the intended read-only
fact-payment modules. Never enable empty-target loader fixtures on the populated
warehouse. Compatible CREATE OR REPLACE preserves the view; commit precedes tests.
Failed acceptance is not automatic rollback: retain view/artifacts and diagnose
without drop, full refresh or reload. No development resource deletion is authorized.

Historical source: 103,886 components; exact payment sum 16008872.12; two
zero-installment, nine zero-value and three not_defined components. These are
overlapping source-quality observations, not revenue or GMV definitions.

Status: COMPLETE. Scoped source/harness reviews approved; offline 55,
adopted payment/runner 137, warehouse/API 1222 (856 deliberate live skips),
native read-only PostgreSQL 45 and physical/access 2 tests passed. Ruff
lint/format 136 reported files, mypy 22 implementation files and offline dbt
parse passed. Known AnyIO alias deprecation warning only.
Source checkpoint e50d47c published clean before first build. First/repeat
each passed one view/all 14 dbt tests in 55.391/57.386 seconds. All 103,886
components/keys, exact 16008872.12 amount and flags 2/9/3 conserved. Independent
guarded raw/staging/core complete ten-field multisets match; native types/
typmods/collations, restricted actual login/role/verify-full TLS and private
API/reader denials verified. Repeat preserves relation identity/owner/grants;
password absent from both retained artifact sets. Database 287,263,891 bytes
is below 400,000,000. See [aggregate evidence](fact-payments-verification.json)
for result nodes and retained artifact paths. Suite timings are not consumer
latency; M5 measured plans/performance/reconstruction remain pending.

Full source/frontend/advisory checks were not rerun for this unchanged
dependency/data-only unit; their 2026-09-22 results remain historical. E2E/
deployment/full governance audit have not run. Next core unit: fact_reviews,
then M5. Governance follows verified Phase 3 completion, before Phase 4.
No project resources were deleted; no dependency/migration/reload occurred.
