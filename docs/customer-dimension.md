# Customer identity dimension

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: code/offline/native COMPLETE; first/physical/repeat acceptance PENDING.

`core.dim_customer` contains one literal `customer_unique_id` per cross-order
identity. Its only column is that text identifier. The accepted source has 99,441
order-linked customer records and 96,096 identities; repeated identities can carry
different addresses and lineage. `DISTINCT` at the declared identity grain uses
explicit `C` collation and retains the identifier exactly, including leading zeroes.

No source row is chosen to represent an identity. Addresses and immutable load/row
lineage remain in `staging.stg_customers`; the planned `int_order_customers` will
preserve those order-linked fields for `fact_orders`. Customer 360, order/spend
metrics, segmentation and a current-address policy belong to later decisions/phases.
No surrogate key or observation counter is needed for this identity relationship.

The model does not filter or repair invalid identifiers. Null or malformed source
identities remain visible and block acceptance. Required/unique dbt tests and a
lowercase 32-character ASCII hexadecimal domain test protect the key. Bidirectional
`EXCEPT ALL` reconciliation compares complete distinct source membership against
the dimension, detecting omitted, extra, changed and duplicated dimension rows.
Repeated source identity is expected; duplicated output identity is a failure.

Offline cases execute actual rendered SQL/generic tests with bounded query-only
SQLite inputs. Native PostgreSQL cases verify actual `DISTINCT`, collation, domain
and multiset behavior using typed synthetic CTEs in read-only transactions. Physical
acceptance independently compares raw/staging/core identities without printing
source values, and checks the actual restricted login, TLS, view owner/types,
private access denials and absence of temporary/backup relations. Native/physical
tests opt in with `COMMERCE_WAREHOUSE_CUSTOMER_DIMENSION_INTEGRATION=1` only.

Use the retained [warehouse/API validation workflow](customer-staging.md).

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select dim_customer
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_customer
```

This is a private view under the owner's Free/views-first decision. Checkpoint code
before first build. Compatible `CREATE OR REPLACE` preserves identity/owner/grants;
the view commits before dbt tests, so failed acceptance is not automatic rollback.
Retain a failed view/artifact and diagnose it without dropping resources. Source
reconciliation can expand eager staging-parent test selection; during bootstrap,
build this dimension before repeating parent tests that now reference it. Historical
test counts describe their dated runs; the runner verifies the current manifest.

No raw reload, migration, dependency, credential, API/UI, deployment or resource
deletion is required. M5 retains measured query plans, consumer-query performance
and reconstruction/recovery acceptance. The comprehensive governance audit remains
after verified Phase 3 completion and before Phase 4.

## Verification — 2026-10-03

81 focused tests and 23 read-only native PostgreSQL cases passed. Retained
warehouse/API regression: 819 passed / 496 deliberately opted-out live checks,
known AnyIO deprecation warning only. Ruff lint/format passed (112 Python files);
mypy passed 22 implementation files; offline dbt parse passed.
Initial collection caught a missing test comprehension bracket; corrected before
these passing runs. Scoped review found no blocking issue.
First live build, physical/access and repeat acceptance: Not yet tested.
