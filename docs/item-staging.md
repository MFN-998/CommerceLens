# Order-item staging milestone

Phase 3 M4, 2026-10-02. Continues the published orders acceptance checkpoint 698191b.
This source-preserving development view needs no migration, source reload, dependency
upgrade, application change or business metric definition.

## Contract and decisions

Retain all seven source fields and both lineage fields. The item key is
(order_id, order_item_id); order_id alone is not unique. Do not aggregate, deduplicate
or multiply rows through joins. Mandatory references target the accepted order, product
and seller staging views through data tests, without adding parent fields to this projection.
IDs retain literal spelling; exact empty becomes NULL. The item sequence is a positive
exact signed-64-bit integer through the existing guarded bigint helper.

Price and freight become numeric(18,2) directly from original raw decimal text, matching
the existing M3 landing contract. Accept ASCII nonnegative digits with an optional one
or two decimal places. Reject signs, exponents, whitespace, nonfinite values, excess scale
(including extra trailing zeroes) and amounts above 9999999999999999.99 before the final
cast. Guard the text operand before numeric conversion, including inline constants.
PostgreSQL otherwise rounds excess scale; this projection must never silently round or
convert through Float64. Zero remains valid, including zero freight. Nonempty rejected
input becomes typed NULL and fails blocking tests; raw and every source row are retained.

Shipping limit uses the existing strict source timestamp helper: canonical ASCII
YYYY-MM-DD HH:MM:SS, real calendar, no fraction/timezone/rollover, and Phase 2 whole-second
bounds. It remains timestamp without time zone; no source timezone is invented.

Shipping-before-purchase and exploratory deadlines beyond 365 days need parent purchase
context. Their explicit flags belong to the planned fact_order_items core model, following
ADR 0003 and the Phase 2 warning policy. Four historical over-one-year rows must remain
visible then; this staging unit neither repairs them nor claims those contextual flags
have already been implemented. No duration or deadline eligibility policy is added.

## Verification and operation

Sixteen dbt data tests cover nine mandatory fields, three parent relationships, composite
grain, lineage uniqueness, source domains and full bidirectional row-multiset reconciliation.
Synthetic fixtures must prove exact decimal boundaries/cent sums, source-format rejection,
fractional/overflow sequence rejection, timestamp preservation and missing-parent failure.
SQLite adapter results do not establish native PostgreSQL casts, typmods or EXCEPT ALL;
separate read-only PostgreSQL fixtures and physical access checks are required.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_items
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_order_items
```

Use [customer staging](customer-staging.md) for retained regression commands, restricted
transformer settings and compatible CREATE OR REPLACE view behavior. A successful view
commit precedes its tests; a failed acceptance is not automatic rollback. Preserve the
view/artifacts and diagnose, with no drop, full refresh or source reload.
Enable COMMERCE_WAREHOUSE_ITEM_INTEGRATION=1 only for the intended read-only modules;
never enable unrelated empty-target loader fixtures against the populated warehouse.

Historical source observations: 112,650 items, exact price sum 13591643.70 and freight sum
2251909.54. These are technical source-column reconciliation values, not GMV, revenue,
profit or assertions that item and payment sums must equal.

Status: COMPLETE. Ruff lint/format passed
(87 Python files), mypy passed (22 implementation files), offline dbt parse passed.
Warehouse/API regression passed: 463 tests, 221 deliberate opt-in skips;
known AnyIO deprecation warning only. Native read-only item cases passed: 83.
First and repeat builds each passed one view and all 16 dbt tests, retaining 112,650 rows.
Actual-login read-only physical/access acceptance passed. Independent exact raw/view
price and freight sums match the historical observations above. Repeat identity/owner/
grants were preserved; transformer password absent from both retained build artifacts.
Database size: 287124627 bytes, below the 400M-byte ceiling.
See [acceptance evidence](item-staging-verification.json). Full source/frontend/advisory
checks were not rerun for this dependency-unchanged data-only unit.
The comprehensive governance audit remains pending verified Phase 3 completion.

References: [PostgreSQL numeric types](https://www.postgresql.org/docs/17/datatype-numeric.html),
[input validation](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-INFO-VALIDITY).
