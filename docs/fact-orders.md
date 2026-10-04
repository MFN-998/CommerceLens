# Order fact

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: COMPLETE; source/offline/native/first live/physical/repeat acceptance passed.

`core.fact_orders` is a private view at **one `order_id`**. It preserves all 22
accepted `stg_orders` columns, including literal status, five timestamps, every
missingness/reversal flag, and order `_load_id`/`_source_row` lineage. The source
snapshot contains 99,441 orders; every status and warning remains represented.

One literal `C`-collated left join to `int_order_customers` adds six fields:
`customer_unique_id`, `customer_zip_code_prefix`, `customer_city`, `customer_state`,
`customer_load_id`, and `customer_source_row`. Mapping lineage is named separately
from order lineage. Repeated cross-order identity keeps each order-associated
source address; no arbitrary current address is selected. A missing mapping
retains the order with NULL enrichment and fails acceptance. A duplicate mapping
must fail grain/count validation, even if both expected and actual joins multiply.

Five date role references are direct casts of the unchanged timestamps:

| Field | Retained source timestamp |
| --- | --- |
| `purchase_calendar_date` | `order_purchase_timestamp` |
| `approval_calendar_date` | `order_approved_at` |
| `carrier_delivery_calendar_date` | `order_delivered_carrier_date` |
| `customer_delivery_calendar_date` | `order_delivered_customer_date` |
| `estimated_delivery_calendar_date` | `order_estimated_delivery_date` |

Purchase and estimate are mandatory. The other three dates are NULL exactly when
their typed events are absent. Recorded events, including reversed lifecycle
dates, must belong to `dim_date`. Source timezone is unspecified: neither a UTC
conversion nor a current-time default is introduced. Exact-empty parsing and
invalid-text rejection remain the responsibility of accepted staging.

There are **33 fields**. Dimension membership is tested without joining redundant
dimension attributes into the fact. All source customer ZIPs belong to the location
domain; missing geolocation evidence is valid and does not exclude an order.
Coverage/ambiguity metadata remains available from `dim_location`.

There are no item/payment/review joins, child-presence flags, monetary metrics,
business eligibility filters, geography representatives, surrogate keys, durations
or separate delivery fact. Independent child facts/mart aggregation follow later.
ADR 0003 requires present, ordered events whenever a later consumer exposes a
duration; it does not require speculative duration fields in this unit.

## Quality and operation

The YAML declares 27 required-field tests, order-key uniqueness, and exact order
status/customer state domains. Three singular tests validate key/ordinal/date
correspondence, full 33-field source reconciliation with independent source-order
cardinality, and required mapping/identity/ZIP/date membership. Text multiset and
join comparisons use literal `C` collation. Parent-date validation inspects distinct
nonnull dates from a materialized fact projection to avoid five expanded source
scans; it does not change the model or remove an assertion.

Offline query-only synthetic fixtures exercise actual projection/test SQL and
configured dbt generic macros. Native read-only PostgreSQL fixtures establish
typed timestamps/date keys, literal collation, NULL behavior, boundary dates and
timezone independence. Physical acceptance compares independent raw/staged/core
expectations, full data conservation, role/TLS/type/collation/ownership and private
API/reader access. Only aggregate diagnostics/metadata are fetched.

Use the [retained warehouse/API validation workflow](customer-staging.md).
Native/physical opt-in: `COMMERCE_WAREHOUSE_FACT_ORDERS_INTEGRATION=1`.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select fact_orders
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_orders
```

Publish a reviewed, validated source checkpoint before first live build. Compatible
`CREATE OR REPLACE` preserves view identity/ownership/grants, but commits before
tests; failed acceptance is not automatic rollback. Preserve view/artifacts and
diagnose. Later child references can expand eager parent test selection; do not
repeat parents that reference an as-yet-unbuilt child.

No migration, reload, package, credential, API/UI/deployment change or project
resource deletion is required. Consumer-query performance/reconstruction remains
M5. The comprehensive governance audit follows verified Phase 3 completion,
before Phase 4.

## Verification — 2026-10-04

Scoped source/offline harness/acceptance-helper review approved. Read-only
preflight passed: required parents present, fact view absent, all 99,441 raw
orders/unique IDs and database 287,222,931 bytes <400,000,000. Offline parse
passed; retained artifacts `.artifacts/dbt/8d56aa1f4d9e4a0892645244105d12c8`.
Candidate offline suite: 104 passed in 1.97 seconds. Existing runner suite:
69 passed in 15.28 seconds. All three test candidates passed AST parsing and
were adopted. Adopted fact suite: 104 passed. Warehouse/API regression:
1075 passed/738 deliberate live opt-out skips, known AnyIO warning
only. Native read-only PostgreSQL: 97 passed. Ruff lint/format passed
(128 reported files); mypy passed 22 implementation files. Scoped
native/physical review approved. Initial adopted lint found two import-group
spacing issues; corrected and all subsequent quality checks passed. No
behavior change or failing fact checks remains.

Source checkpoint `b57a416` was published clean before first live build.
First build passed one view/all 33 tests in 115.488 seconds; artifacts:
`.artifacts/dbt/ef1e2c522e704d11857a907edcb9da56`. Physical/access: **2 passed**. Independent raw/stage/mapping/fact full fields,
both lineages, original warning counts, 278 uncovered rows and optional NULL
dates conserved. Actual restricted login/role/verify-full TLS, inherited
types/collation and private API/reader denials verified. Repeat acceptance **FAILED** with `DbtError`; interrupted artifacts
`.artifacts/dbt/8b6d4807b6544cb89fa67dd409a029c0` contain no complete
`run_results.json`. Exact suppressed reason was not retained. The first
115.488-second workload makes the existing 120-second overall budget a
possible cause; the original failure's cause remains unconfirmed. View and all
artifacts are preserved; no model/source change or rollback/deletion performed.

Scoped review approved a workload budget correction: parse/debug remain at
120 seconds; exact approved build/test suites allow 180 seconds. Individual
SQL 60s/lock 10s/idle transaction 60s, one thread, zero retries and every
result/privacy gate remain unchanged. Initial runner checks had three debug
mock failures (assumed target-path was available for debug), corrected to shared
log-path. Final runner 78 passed; warehouse/API 1084 passed/738 deliberate
live skips, known AnyIO warning only. Ruff lint/format 128 files, mypy 22
source files and offline parse passed. Retained parse artifacts:
`.artifacts/dbt/536178186f66417d93d5cbdec0686329`. Corrected fixture
lint/format and scoped independent review passed. The reviewed runner
checkpoint `8c170b6` was published clean before repeat retry.
Repeat retry passed one view/all 33 tests in 115.521 seconds.
Artifacts: `.artifacts/dbt/063713da68cf4298af22596a04a52285`. All 99,441 orders/
96,096 identities/278 uncovered rows, lifecycle flags and NULL-date counts
were conserved: 160 missing approval, 1,783 missing carrier delivery and
2,965 missing customer delivery. Relation identity/ownership/grants remained
unchanged; password absent from first/successful-repeat artifacts. Database
287,247,507 bytes is below the 400,000,000-byte ceiling. See
[aggregate acceptance evidence](fact-orders-verification.json). The failed
attempt remains retained; no unresolved fact-order acceptance failure remains.

Accepted models remain unchanged. Suite timing is not consumer latency;
M5 must measure consumer query plans/performance and reconstruction/recovery.
Scoped final handoff review and complete staged-content/history secret scans passed.
Publish the acceptance checkpoint and confirm clean/synchronized Git before close.

The [item fact](fact-order-items.md) is now accepted at its composite grain,
preserving exact components, source lineage and shipping warnings. Next core
unit: `fact_payments`; see the [Phase 3 plan](phase-3-plan.md).
