# Customer staging milestone

Phase 3 M4; implementation prepared 2026-09-27 from verified live setup 142277c.
The selected build/test commands also approve stg_sellers, stg_category_translation and
stg_products, stg_orders, stg_order_items, stg_order_payments, stg_order_reviews and
stg_geolocation; see their guides in the [Phase 3 plan](phase-3-plan.md). All nine
source staging models are verified. Dimensions/facts and marts remain
pending; no business KPIs or Phase 4 analysis are added.

## Data contract

staging.stg_customers retains one source row per customer_id and both lineage fields.
customer_unique_id may repeat. IDs, ZIP text/leading zeros, city/state spelling and
whitespace are preserved. Only exact empty strings become NULL. Missing mandatory data,
duplicate keys/lineage and invalid formats fail tests without repairing or removing rows.
Data tests compare complete raw/staging row multisets in both directions with EXCEPT ALL.

## Non-deleting execution

The owner forbids unapproved deletion, including automatically generated resources.
The project's Postgres view materialization uses CREATE OR REPLACE VIEW rather than the
standard dbt temporary/backup swap. Existing ownership, grants and dependent objects are
preserved; replacing a non-view or changing existing column types/order fails. Hooks,
SQL headers and grant overrides are rejected until separately reviewed. PostgreSQL commits
the view before dbt data tests: failing tests mean failed acceptance, not automatic rollback
of a successfully built view. Preserve the relation and diagnose; no automatic drop/cleanup.

Every dbt invocation retains a unique ignored .artifacts/dbt directory. Parse uses synthetic
settings; build/test use only protected transformer settings. Classic parser is explicit;
telemetry and file logs stay disabled. Test failure storage is false, with test schema staging.
Successful build/test status also requires nonempty matching model/test run-results evidence.
No unrestricted selector, full refresh, clean or package-install command is exposed.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_customers
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_customers
```

## Offline validation without deletion

Use the installed locked environment; direct execution avoids automatic dependency changes.
The retained tmp_path fixture allocates UUID directories without pytest cleanup or symlinks.
Run warehouse/API tests with plugin autoload disabled, system-stream capture and no cache.
Do not run the existing full check.ps1 unchanged: source tests delete generated fixture data
and Next builds clean generated output. Those paths need specific approval or a separately
reviewed non-deleting workflow; they were not needed for this data-only change.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$warehouseTests = @(Get-ChildItem -LiteralPath tests -Filter 'test_warehouse*.py' -File | ForEach-Object { $_.FullName })
.venv/Scripts/python.exe -B -m pytest @warehouseTests api/tests -o 'addopts=-ra' --capture=sys -p no:cacheprovider
.venv/Scripts/python.exe -B -m ruff check . --no-cache
.venv/Scripts/python.exe -B -m ruff format --check . --no-cache
.venv/Scripts/python.exe -B -m mypy --cache-dir=nul
```

These commands are verified on Windows; nul is the Windows null device. Restore any changed
environment settings in an interactive shell. Live checks require separate deliberate opt-in;
do not run existing empty-target/loading fixtures against the populated warehouse.

Offline SQLite SELECT/VALUES cases exercise the actual portable projection with synthetic
inputs. They do not prove PostgreSQL regex/types/EXCEPT ALL or live privileges. Full gate
results from 2026-09-22 remain historical; this milestone records its own relevant validation.

References: [dbt data tests](https://docs.getdbt.com/docs/build/data-tests),
[PostgreSQL CREATE VIEW](https://www.postgresql.org/docs/17/sql-createview.html).

## Acceptance status

Offline focused checks passed (47); type checking passed (22 implementation files).
Warehouse/API regression passed: 168 tests, 14 opt-in live tests skipped; documented AnyIO
warning only. Initial parser/options and API fixture-scope errors were fixed before acceptance.
The retained fixture is at repository-root conftest.py, covering API and warehouse tests.

Live first and repeat builds passed: one view and 12 dbt data tests each. The read-only
customer integration test passed separately. All 99,441 source rows are retained; types,
ownership, API-role denials and absence of intermediate/backup relations were verified.
The repeat build preserved relation OID, owner and grants. Database size was
287,059,091 bytes. No transformer password was found in repeat artifacts.
See [acceptance evidence](customer-staging-verification.json).

This atomic customer unit is COMPLETE. See the [Phase 3 plan](phase-3-plan.md) for
current remaining staging/core/M5 work. No dataset reload, package upgrade, deletion or deployment occurred.
The old full source/frontend gate was not rerun because its automatic cleanup requires
approval/adaptation; current implementation/dependencies do not change those components.

To repeat the read-only acceptance test, set COMMERCE_WAREHOUSE_CUSTOMER_INTEGRATION=1
and use the retained pytest command above with tests/test_warehouse_customer_integration.py.
Restore the environment flag afterward. For a compatible SQL fix, edit the tracked model,
validate, then use the selected build command; do not drop/recreate the view. Incompatible
schema changes need a separately reviewed non-deleting migration or specific deletion approval.
