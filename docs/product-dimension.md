# Product dimension

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: code/offline/native COMPLETE; first/physical/repeat acceptance PENDING.

`core.dim_product` retains one source `product_id`, all 20 accepted staging fields
and their types, including immutable lineage, original length-name spellings,
nullable attributes and missingness/zero-weight flags. A left join to the literal
Portuguese category translation appends nullable `product_category_name_english`
and required `is_untranslated_category`, giving 22 fields.

The known 610 missing-category products retain `is_missing_category=true` with no
English label and `is_untranslated_category=false`. The 13 products with a present
category but no lookup entry retain `is_untranslated_category=true`. No invented
“unknown” label merges these different conditions. Zero weight and missing optional
measurements remain source observations, without eligibility or KPI decisions.

The lookup uses explicit `C` equality, preserving case, accents and whitespace.
Repeated English labels are allowed; the Portuguese lookup key must be unique.
Duplicate matching lookup rows are not deduplicated or assigned a representative
English label. They produce a failed grain/conservation check. A matched lookup
with null English fails the coverage-domain check instead of becoming a warning.

Required lineage/ID/boolean tests and product uniqueness protect the output shape.
Domains validate ID/ordinal, missing-category flag and category/English/coverage consistency. Full
bidirectional `EXCEPT ALL` compares all 22 expected fields against actual output;
an independent source-versus-dimension row-count check also catches lookup fanout
even if the same duplicated lookup appears in expected and actual joins. Original
numeric parsing/domains remain in the accepted staging boundary; core does not recast.

Offline tests execute actual SQL and installed YAML-configured generic macros on
query-only SQLite fixtures. Native tests use typed read-only PostgreSQL CTEs with
binary results to preserve double precision under current text-output settings.
Physical acceptance returns only metadata and aggregates, checks source membership,
all retained fields, missing/untranslated/zero counts, actual restricted login/TLS,
view owner/types and API/reader denials. Opt in only with
`COMMERCE_WAREHOUSE_PRODUCT_DIMENSION_INTEGRATION=1`.

Use [retained warehouse/API validation](customer-staging.md).

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select dim_product
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_product
```

This is a private Free/views-first view. Publish a verified code checkpoint before
first build. Compatible `CREATE OR REPLACE` preserves identity/owner/grants, but
commits before dbt tests: failed acceptance is not rollback. Preserve a failed
view/artifacts and diagnose. During bootstrap, build this child before repeating
parent tests that now reference it through eager selection. Historical parent test
counts remain dated evidence; the runner checks the current selected manifest.

No source reload, migration, dependency, credential, API/UI, deployment or resource
deletion is required. Measured consumer-query performance and reconstruction remain
M5. Comprehensive governance runs only after verified Phase 3, before Phase 4.

## Verification — 2026-10-03

126 focused tests and 58 read-only native PostgreSQL cases passed. Retained
warehouse/API regression: 884 passed /555 deliberately opted-out live tests,
known AnyIO warning only. Ruff lint/format passed (116 Python files); mypy passed
22 implementation files; final offline dbt parse passed.
Initial native run: 57 passed/2 failed. Added missing-category flag consistency
and corrected an overly strict domain expectation about exact English spelling,
already protected by reconciliation. Subsequent full native run passed.
First live build, physical/access and repeat acceptance: Not yet tested.
