# Order staging milestone

Phase 3 M4, 2026-10-01. Continues the verified product acceptance checkpoint 7a2e1e6.
This is a source-preserving view, with no migration, source reload, dependency change,
business KPI, child join or application change.

## Contract and decisions

One row per order_id preserves both raw lineage fields and all eight source fields.
The mandatory customer_id references the existing order-linked stg_customers record.
Status remains the exact source value; do not infer completion from recorded events.

Five dates become timestamp without time zone. The source provides no timezone, so
conversion must not manufacture UTC or depend on the session timezone. Purchase and
estimated delivery are mandatory; approval, carrier handoff and customer delivery are
nullable. Exact empty strings become NULL; whitespace is not treated as missing.

Accept only canonical ASCII YYYY-MM-DD HH:MM:SS, real calendar dates, hours 00-23 and
minutes/seconds 00-59. Preserve the Phase 2 nanosecond-compatible domain at whole seconds:
1677-09-21 00:12:44 through 2262-04-11 23:47:16 inclusive. Validate before casting and
guard the text operand itself so inline constants cannot cause planning-time cast errors.
Nonempty rejected input remains present in raw, produces typed NULL and fails a blocking
aggregate source-domain test. It cannot pass as optional original missing data.

Source-missing flags describe the three optional raw fields, independent of parsing.
Three delivered-missing diagnostics describe typed event absence for exact delivered
status. Six named flags cover every reversed pair in the purchase -> approval -> carrier
-> customer event chain; absent operands yield false. Estimates are not actual events.
Do not repair dates, filter anomalous orders, calculate durations or define eligibility.

The warehouse intentionally rejects parser quirks observed in the installed pandas
Phase 2 parser: nonpadded dates, leap-second rollover and dynamic now/today text.
That stricter guard follows the ADR's fixed source format and no invented event policy.
Recommended deferred parser debt; owner: project maintainer. The strict warehouse guard
mitigates risk for the verified snapshot. Revisit before accepting a different source version;
do not reopen completed phases or run the comprehensive governance audit prematurely.

Historical source warnings are retained: delivered orders without approval/carrier/customer
events (14/2/8); carrier before purchase (166), carrier before approval (1,359), customer
before approval (61), customer before carrier (23). Approval before purchase and customer
before purchase are zero. Counts overlap and are source-quality observations, not KPIs.

## Verification and operation

The selected model has 25 dbt data tests: mandatory values, grain, customer relationship,
exact status domain, non-null diagnostic flags, lineage uniqueness, blocking source domains
and complete bidirectional row-multiset reconciliation. Synthetic cases exercise missing
and invalid dates, calendar and representability boundaries, all reversal flags, unchanged
status and source IDs. Native read-only PostgreSQL tests are required because a SQLite
adapter cannot establish PostgreSQL parser or physical type behavior.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_orders
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_orders
```

Follow [customer staging](customer-staging.md) for retained regression commands and the
restricted transformer. The compatible CREATE OR REPLACE materialization preserves
identity/owner/grants and does not delete project resources. A view commits before data
tests; failed acceptance requires diagnosis and does not imply automatic rollback.
Read-only order checks use COMMERCE_WAREHOUSE_ORDER_INTEGRATION=1 for the intended modules
only. Never enable unrelated empty-target loading tests against the populated warehouse.

Status: COMPLETE. Ruff lint/format passed (83 Python files), mypy passed
(22 implementation files), offline dbt parse passed, and warehouse/API regression passed
(329 tests, 137 deliberate opt-in skips; known AnyIO warning). All 87 native read-only
order cases and the separate actual-login physical/access acceptance passed.
First and repeat builds each passed one view and all 25 dbt tests, retaining 99,441 rows.
Repeat identity/owner/grants were preserved; all diagnostic flag counts matched independent
raw-source checks. Source-missing approval/carrier/customer counts are
160/1,783/2,965;
delivered-missing and reversal counts match the historical observations above.
No transformer password was found in either build's retained artifacts. Database size:
287116435 bytes, below the 400M-byte ceiling.
See [acceptance evidence](order-staging-verification.json). Full source/frontend/advisory
checks were not rerun for this dependency-unchanged data-only unit.
The comprehensive post-Phase-3 governance gate remains pending full Phase 3 completion.

Reference: [PostgreSQL date/time types](https://www.postgresql.org/docs/17/datatype-datetime.html),
[input validation](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-INFO-VALIDITY),
[CASE evaluation](https://www.postgresql.org/docs/17/functions-conditional.html).
