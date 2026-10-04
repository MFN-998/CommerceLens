# Order-item fact

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: COMPLETE; source/offline/native/first live/physical/repeat acceptance passed.

`core.fact_order_items` is a private view at **(order_id, order_item_id)**.
All nine accepted staging item fields remain unchanged, including source lineage,
the literal order/product/seller references, shipping deadline and exact
`numeric(18,2)` price/freight. Zero remains zero; these are source components,
not revenue/GMV definitions or payment-reconciliation assertions.

One literal `C`-collated LEFT JOIN to accepted `fact_orders` adds purchase context
and separately named `order_load_id`/`order_source_row`. A missing parent retains
the item with NULL context and fails required/reference checks. Duplicate parent
fanout must fail the independent source-item count and composite grain even when
expected/actual joins both multiply. Product/seller membership uses separate tests,
without redundant attribute joins.

Two boolean flags conserve the Phase 2 warnings: shipping deadline before purchase
and exact elapsed interval strictly greater than 365 days. Equality and exactly
365 days are unflagged; one second beyond is flagged. This is neither calendar-year
arithmetic nor date truncation. Absent events produce false flags but still fail
mandatory fields; false never establishes business eligibility. Source timestamps
have no timezone; no UTC/current-time default is invented. The shipping date key
is a direct calendar-date cast and must belong to accepted `dim_date`.

There are **15 fields** and **19 dbt tests**: 15 required columns and four singular
checks for composite grain, domains/chronology, full-field source multiset with an
independent source count, and core order/product/seller/date references.
No durations, status filtering, quantity/revenue fields, child joins, aggregations,
deduplication, migration, reload or dependency change is introduced.

## Verification and operation

Offline fixtures exercise actual model/test SQL and installed configured dbt macros;
SQLite adaptations cannot establish native numeric typmods, interval arithmetic,
collation or timestamp types. Native read-only PostgreSQL and independent raw/stage/
core physical acceptance verify those semantics and exact money/provenance separately.
Only aggregate diagnostics and metadata are fetched from the real snapshot.

Use the [retained warehouse/API workflow](customer-staging.md). Deliberate native/
physical opt-in: `COMMERCE_WAREHOUSE_FACT_ITEMS_INTEGRATION=1`.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select fact_order_items
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_order_items
```

Publish a reviewed source checkpoint before first build. Compatible non-deleting
CREATE OR REPLACE preserves relation identity/owner/grants and commits before tests;
failed acceptance is not automatic rollback. Preserve view/artifacts and diagnose.
Overall selected suite budget is 180 seconds; SQL/lock/idle transaction limits remain
60/10/60 seconds with one thread and zero retries. Suite timings are not consumer
latency; measured consumer plans/performance and reconstruction/recovery remain M5.

Historical source components: 112,650 items; price 13591643.70, freight 2251909.54;
four shipping deadlines beyond 365 days. Recheck source chronology independently.
Scoped source/harness review approved. Candidate offline 79 passed (0.85s);
adopted item/runner focused 159 passed (19.11s); warehouse/API regression
1165 passed/809 deliberate live skips (28.50s), known AnyIO warning only.
All three harnesses AST-checked/adopted; imports spaced for repository Ruff
classification without behavior change. Ruff lint/format 132 reported files
and mypy 22 implementation files passed. Offline parse passed; retained:
`.artifacts/dbt/6179cb386aca49eca12b134cef5a6ed3`. Native read-only PostgreSQL
69 passed (96.97s) on adopted SQL, byte-identical to candidate source.

Read-only preflight confirmed view absent/parents present, 112,650 rows/keys,
exact source money above, 0 before-purchase/4 beyond-365-day warnings and
database 287,247,507 bytes <400,000,000. Initial acceptance-helper quoting
error prevented execution; corrected before preflight, no DB mutation.
Source checkpoint `a047ecf` published clean before build. First passed
one view/all 19 tests in 106.982 seconds; artifacts `.artifacts/dbt/0e137cd093ad41179fb41a17662131a3`.
Physical/access: **2 passed**. Independent raw/stage/core full 15-field
multisets, exact source money and both lineages/context/flags/direct date
matched; inherited numeric typmods/types/collation and restricted actual
login/role/verify-full TLS/private API/reader denials verified.
Repeat passed one view/all 19 tests in 106.281 seconds; artifacts
`.artifacts/dbt/d1371f62447c4a62ac1c279074f56e7e`. All item counts/keys/exact money/
chronology counts and view identity/owner/grants remained unchanged. Password
absent from first/repeat artifacts; database 287,255,699 bytes <400,000,000.
See [aggregate acceptance evidence](fact-order-items-verification.json).
The [payment fact](fact-payments.md) is accepted, retaining all components and
source warnings. Next core unit: fact_reviews.
No project resources are deleted. The comprehensive governance audit follows
verified Phase 3 completion, before Phase 4.
