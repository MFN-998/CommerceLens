# Order-linked customer mapping

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: source/offline/native checks complete; first live/physical/repeat acceptance pending.

`core.int_order_customers` retains one source `customer_id` and exactly seven
accepted staging fields: `_load_id`, `_source_row`, `customer_id`,
`customer_unique_id`, `customer_zip_code_prefix`, `customer_city`, `customer_state`.
Types and collation are inherited without recasts. It lives in the intermediate
model directory and private core schema; no extra schema or service is needed.

This reusable mapping connects the order-linked customer record to cross-order
identity while keeping the purchase-associated address and source provenance.
The historical snapshot has 99,441 records and 96,096 distinct identities.
Repeated identity, different addresses and load/row lineage remain visible.
Only `customer_id` is the row key; identity is deliberately not unique here.

There is no join, filtering, deduplication, normalization, surrogate, current
address selection, geographic representative, metric or additional coverage flag.
Exact-empty parsing and upstream raw contracts remain at accepted staging.
Null/invalid keys remain present and block validation, rather than disappearing.
Leading zeroes, one-to-five-digit ZIPs, city case/accents/whitespace and state
spelling are retained literally.

Required fields, customer-key uniqueness and all 27 source state values are
tested. Domains validate lowercase ASCII hexadecimal IDs, literal ZIP grammar
and positive source ordinal. Full bidirectional `EXCEPT ALL` compares all seven
fields with explicit `C` text collation. Separate `NOT EXISTS` checks require
identity membership in `dim_customer` and ZIP membership in `dim_location`.
Missing parents fail; geography coverage is not required. All 278 customer rows
without geolocation evidence remain valid, because their ZIPs belong to the
location domain. Parent dimensions retain their own grain tests; this mapping
does not choose among duplicate parent rows or silently repair missing parents.

Offline query-only synthetic fixtures exercise actual SQL/tests and configured
generic macros. Native typed read-only PostgreSQL fixtures cover exact fields,
literal text, repeated identities/addresses/lineage, corrupt output and parent
membership. Physical checks independently compare all raw/staged/core fields,
types/collation, actual restricted login/TLS/ownership and denied API/reader
access; only metadata and aggregate diagnostics are fetched.

Use [retained warehouse/API validation](customer-staging.md).
Native/physical tests opt in with `COMMERCE_WAREHOUSE_ORDER_CUSTOMERS_INTEGRATION=1`.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select int_order_customers
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select int_order_customers
```

Publish a validated code checkpoint before first build. Compatible `CREATE OR
REPLACE` preserves view identity/ownership/grants, but commits before tests;
failed acceptance is not automatic rollback. Preserve view/artifacts and
diagnose. Child reconciliation/relationships can expand eager parent selection;
build this mapping before repeating parent tests that refer to its pending view.

No reload, migration, package, credential, API/UI, deployment or resource deletion
is required. Consumer-query performance/reconstruction remains M5. Governance
runs after verified Phase 3 completion and before Phase 4.

## Verification — 2026-10-04

The scoped source review approved the contract. Candidate offline tests: 46
passed. Adopted focused suite: 113 passed; warehouse/API regression: 969 passed
/639 deliberate live opt-out skips, known AnyIO warning only. Native read-only
PostgreSQL: 44 passed. Ruff lint/format passed (124 reported files); mypy passed
22 implementation files. Offline parse passed; retained artifacts:
`.artifacts/dbt/b874d3838e1c44f4b46090388bb16707`.

First live build, physical/access and repeat acceptance: **Not yet tested**.
No mapping view has been built; accepted date checkpoint `ca44c12` is preserved.

Next core unit: `fact_orders`, retaining all orders and lifecycle/quality flags
at one order, through this mapping and accepted dimensions; no child fanout or
business eligibility policy.
