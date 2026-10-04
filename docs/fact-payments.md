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

Status: source/offline/native COMPLETE; first live/physical/repeat pending.
Scoped source/harness reviews approved. Candidate offline 55 passed (0.43s);
adopted payment/runner focused 137 passed (15.64s); warehouse/API regression
1222 passed/856 deliberate live opt-out skips (27.04s), known AnyIO warning
only. Native read-only PostgreSQL 45 passed (52.90s). Adopted Ruff lint/format
136 reported files and mypy 22 implementation files passed. Offline parse
retained: `.artifacts/dbt/6f7b26ba4fd14ffb9be2b953a7a37e57`. Read-only
preflight confirmed expected counts/sum/flags, zero missing orders and
database 287,255,699 bytes <400M; view absent and parents present.
Publish a reviewed source checkpoint and confirm clean Git before first build.
First live/physical/repeat: **Not yet tested**.
Full source/frontend/advisory checks remain historical 2026-09-22 for this unchanged
dependency/data-only unit. E2E/deployment/full governance audit are not performed;
the governance gate follows verified Phase 3 completion, before Phase 4.
