# Payment staging milestone

Phase 3 M4, 2026-10-02. Continues published item acceptance checkpoint 05dc235.
This source-preserving view uses existing numeric helpers. No dependency, migration,
source reload, application feature or business metric definition is required.

## Contract and decisions

Retain all five source fields and both lineage fields at
(order_id, payment_sequential). An order can have multiple payment components; do not
aggregate, deduplicate or join parent fields into this projection. The mandatory order
reference is tested against stg_orders. Exact empty text becomes NULL; IDs and methods
retain literal spelling. Only credit_card, boleto, voucher, debit_card and not_defined
are accepted methods. Case changes and unknown methods fail validation.

Payment sequence is a positive exact signed-64-bit integer; installments is nonnegative.
Use the existing guarded bigint helper, without fractional truncation. Payment value
uses the existing guarded money helper directly from raw text as numeric(18,2), with no
float intermediate or rounding. Its M3 grammar is ASCII nonnegative digits, optionally
one or two decimal places, at most 9999999999999999.99. Invalid or missing mandatory
values become typed NULL and block acceptance without dropping source rows.

Preserve zero installments, zero payment value and not_defined methods with explicit
is_zero_installments, is_zero_payment_value and is_undefined_payment_type flags.
Invalid/missing typed numeric values produce false zero flags, never a fabricated zero.
An actual not_defined method remains flagged even when another field is invalid.
Flags can overlap. They are quality observations, not eligibility or repair rules.

## Verification and operation

Sixteen dbt tests cover mandatory source/lineage and boolean fields, the order
relationship, literal method vocabulary, composite grain, lineage uniqueness, source
domains and full bidirectional row-multiset reconciliation, including the flags.
Focused synthetic fixtures test actual SQL wiring, flag combinations, invalid input,
split payments and count-preserving corruption. Native read-only PostgreSQL fixtures
establish actual casts and multiset behavior; separate physical access checks verify
types, role ownership and denied API access. Shared numeric boundary tests remain in
the accepted item suite rather than being duplicated here.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_payments
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_order_payments
```

Use [customer staging](customer-staging.md) for retained regression commands and
restricted transformer settings. Compatible CREATE OR REPLACE preserves the view;
view commit precedes data tests. Failed acceptance is not automatic rollback: retain
the view/artifacts and diagnose without drop, full refresh or source reload.
Enable COMMERCE_WAREHOUSE_PAYMENT_INTEGRATION=1 only for the intended read-only modules.
Never enable unrelated empty-target loader fixtures against the populated warehouse.

Historical source observations: 103,886 rows, exact payment sum 16008872.12,
two zero-installment rows, nine zero-payment rows and three not_defined methods.
These are source reconciliation values and overlapping quality observations, not
revenue, GMV, profit or assertions that payment and item sums must equal.

Status: COMPLETE. Ruff lint/format
passed (91 Python files), mypy passed (22 implementation files), offline dbt
parse passed. Warehouse/API regression: 533 passed, 263 deliberate opt-in
skips; known AnyIO deprecation warning only. Native read-only payment fixtures: 41
passed. First and repeat builds each passed one view and all 16 dbt tests. Actual-login
read-only physical/access acceptance passed. All 103,886 source rows and the exact
payment sum 16008872.12 were retained, including two zero-installment, nine zero-value
and three undefined-method rows. Repeat identity/owner/grants remained unchanged;
password absent from both retained build artifacts. Database size 287132819
bytes, below 400M. See [acceptance evidence](payment-staging-verification.json).
Full source/frontend/advisory checks were not rerun for this dependency-unchanged
data-only unit; their existing 2026-09-22 results remain historical.
The comprehensive governance audit follows verified Phase 3 completion, before Phase 4.
