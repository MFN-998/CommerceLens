# Seller dimension

Phase 3 M4, per [ADR 0003](decisions/0003-warehouse-contract.md).
Status: code/offline/native COMPLETE; live first/physical/repeat acceptance PENDING.

`core.dim_seller` keeps one row per source seller_id, all six accepted staging
fields (including source load/ordinal lineage) and `has_geolocation`. It joins the
unique [location dimension](location-dimension.md) by literal ZIP, preserving seller
city/state spelling, Unicode, whitespace and leading zeroes. It does not choose a
canonical city/state/coordinate or attach every geolocation observation to a seller.

`has_geolocation=false` is a retained seller ZIP without observation evidence.
A missing dimension reference leaves this field null and fails validation; it must
not be zero-filled into a legitimate coverage warning. All 3,095 historical seller
rows, including seven uncovered rows, must remain unchanged.

Seven not-null tests, seller uniqueness, a required ZIP relationship and two singular
tests cover domains and complete bidirectional multiset reconciliation. Expected
coverage is independently reconstructed from a unique geolocation ZIP set. This
detects false dimension coverage, missing references, changed fields/lineage, omitted
uncovered rows and duplicated joins. Required domains preserve existing lower-case
hex IDs, one-to-five ASCII digit ZIPs, positive ordinals and 27 state abbreviations.

Use the retained [warehouse/API checks](customer-staging.md). Offline synthetic SQL
tests do not replace native PostgreSQL types/collation checks. Native/physical tests
opt in with `COMMERCE_WAREHOUSE_SELLER_DIMENSION_INTEGRATION=1`; they are read-only.
No loader or other live integration flags are enabled. First/physical/repeat acceptance
checks actual login/TLS, private view ownership/types, exact 3,095 source/core rows,
seven uncovered rows, API/mart-reader denials, identity/grants, artifact secrecy and
the 400 MB storage guard. No migration, raw reload or resource deletion is needed.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select dim_seller
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_seller
```

Build/test uses the protected development transformer configuration. Checkpoint code
before the first build. Compatible `CREATE OR REPLACE` retains identity/owner/grants;
view commits precede tests, so failed acceptance is not rollback. Preserve failed
artifacts/view, record the failure and resume its diagnosis without dropping anything.

Adding the seller-to-location relationship can expand eager parent test selection.
Historical location test counts remain evidence of their actual runs. While the seller
view has not yet been built, run the selected seller build first rather than repeating
parent model tests that now depend on the pending child view. The runner checks the
current manifest's full selected test set.

No API/UI, business KPI, credentials/dependencies, deployment or comprehensive audit
belongs to this unit. Query-plan/performance/reconstruction work remains M5; the full
governance audit follows verified Phase 3 completion, before Phase 4.

## Verification — 2026-10-03

87 focused offline/runner checks, 797 retained warehouse/API regression tests and
30 read-only native PostgreSQL cases passed. The 472 live checks in the regression
were deliberately opted out; known AnyIO warning only. Ruff lint/format passed
(108 Python files), mypy passed 22 implementation files, offline dbt parse passed.
First live view build, actual physical/access and repeat acceptance are not yet tested.
