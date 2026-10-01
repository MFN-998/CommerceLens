# Product staging milestone

Phase 3 M4, 2026-10-01. Continues the verified customer/seller/category baseline b7ec0bb.
The output remains a view on the dedicated development warehouse. No dependencies,
migrations, source reload, KPI definitions or application changes are required.

## Contract and engineering decisions

One row per product_id, preserving both raw lineage columns and all nine source fields.
Keep the original source column names, including product_name_lenght and
product_description_lenght, consistent with the existing Phase 2 dictionary.
Category text keeps its spelling, accents, case and whitespace; exact empty text becomes
NULL. Do not join translations here: the planned dim_product owns that optional enrichment.

Three optional count/length attributes become bigint. Conversion checks decimal/scientific
syntax, exact integrality and signed-64-bit representability before casting; no intermediate
float or silent fractional rounding. Four optional weight/dimension attributes become double
precision, matching the Phase 2 physical-measure contract. All seven domains are nonnegative.
Zero remains zero. Each optional field has a source-missing flag; zero weight has its own flag.
Missing flags describe exact raw empty/NULL, so invalid nonempty input cannot masquerade as
original missing data.

Guarded expressions retain malformed rows with an unrepresentable typed value as NULL;
blocking data tests count nonempty raw values that failed conversion. Such a build is not
accepted. Immutable raw text remains available for diagnosis. No filtering, imputation,
deduplication or arbitrary category replacement is permitted.

PostgreSQL validates its supported numeric representations before casting. In particular,
extreme floating underflow is rejected rather than manufacturing zero; pandas can accept
such text as zero. Numeric whitespace handling follows the warehouse's documented SQL
grammar; source text is unchanged in raw. These representability limits are explicit and
must be reconsidered for a new source version with different numeric syntax.

Historical Phase 2 observations: 32,951 products; 610 missing values each in category,
name length, description length and photo quantity; two missing values each in weight and
dimensions; four zero weights. Thirteen nonempty product categories lack translation
coverage. Counts overlap and are diagnostic observations, not repaired values or business KPIs.

## Verification and operation

Tests must cover mandatory lineage/ID, grain, domains, source-to-view full row multiset
reconciliation, and every quality flag. Synthetic fixtures verify preservation, missingness,
zero/negative values, invalid numeric input and exact integer boundaries. Native read-only
PostgreSQL VALUES/CTE checks verify the actual compiled projection and blocking domain query;
SQLite alone does not prove PostgreSQL conversion behavior.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_products
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_products
```

Follow [customer staging](customer-staging.md) for retained regression commands, restricted
transformer settings and compatible view rebuild behavior. Data tests follow the view commit;
a failed test requires diagnosis and is not automatic rollback. No full refresh or arbitrary
selector is exposed. Read-only product tests use COMMERCE_WAREHOUSE_PRODUCT_INTEGRATION=1;
enable only the intended modules and never unrelated empty-target loading fixtures.

Repository validation passed: Ruff lint/format (79 files), mypy (22 implementation files),
241 warehouse/API tests with 49 deliberate live skips, and 31 native read-only synthetic
tests. The planning-time cast failure was corrected and has a dedicated regression test.
Status: COMPLETE. First and repeat builds each passed one view and all 16 dbt tests.
Physical/access acceptance passed with the actual restricted transformer login. All
32,951 rows and expected source-quality counts are preserved. Repeat identity/owner/
grants were unchanged; no transformer password was found in repeat artifacts. Database
size: 287100051 bytes, below the 400M-byte ceiling.
See [acceptance evidence](product-staging-verification.json). Source/frontend/advisory
checks were not rerun for this dependency-unchanged data-only unit.
No comprehensive post–Phase 3 governance audit yet; the Phase 3 exit condition is still pending.

References: [PostgreSQL numeric types](https://www.postgresql.org/docs/17/datatype-numeric.html),
[input validation](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-INFO-VALIDITY).

Native fixtures use materialized input to match table-column execution and per-case
savepoints for isolation. Helpers also guard inline constants before immutable casts;
see [PostgreSQL CASE behavior](https://www.postgresql.org/docs/17/functions-conditional.html).
