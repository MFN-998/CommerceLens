# Seller staging milestone

Phase 3 M4, 2026-09-27. Uses the existing view materialization, transformer profile,
retained artifacts and bounded selected build/test commands. No dependency, migration,
raw reload, business KPI or application change.

## Contract and decisions

staging.stg_sellers retains one source row per seller_id with both lineage fields.
All four source fields are mandatory. IDs, ZIP prefixes (including leading zeros),
city spelling, accents, case and whitespace are preserved. Only exact empty text becomes
NULL. Invalid or duplicate rows are retained and fail tests, never silently repaired.
The seven Phase 2 geography coverage gaps remain warnings; no geography join filters
sellers or invents a canonical location.

Eleven dbt tests cover six non-null columns, seller key uniqueness, state membership,
ID/ZIP/ordinal domains, composite lineage uniqueness and full row reconciliation
with EXCEPT ALL in both directions. Synthetic tests exercise the actual projection;
separate live acceptance checks physical types, counts, ownership and API-role denial.

## Validation and operation

Follow [customer staging](customer-staging.md) for the retained regression commands,
artifact policy and failed-build recovery. Select exactly stg_sellers for this unit:

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_sellers
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_sellers
```

The opt-in read-only acceptance test is tests/test_warehouse_seller_integration.py
with COMMERCE_WAREHOUSE_SELLER_INTEGRATION=1. Do not enable unrelated live loading fixtures.
Compatible view rebuilds preserve identity, ownership and grants; tests run after the view
commit, so a failed data test means failed acceptance and requires diagnosis.

Status: implementation prepared; repository and live acceptance pending. Do not claim
this unit complete until its live evidence and final checkpoint are recorded.
