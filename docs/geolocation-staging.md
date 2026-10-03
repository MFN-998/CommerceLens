# Geolocation staging milestone

Phase 3 M4, 2026-10-03. Continues review acceptance and the approved cleanup checkpoint.
Reuse the existing guarded double helper; no dependency, migration, source reload or
business KPI change is needed.

## Contract and decisions

Retain all five source fields and both lineage fields for every source observation.
The only observation identity is (_load_id, _source_row). Neither ZIP nor the five
source fields are unique: keep repeated ZIPs and exact duplicates, without selecting
a representative city/coordinate, joining observations to orders or filtering rows.

ZIP/city/state preserve literal source spelling, leading zeroes, Unicode and whitespace.
Only exact empty text becomes NULL. ZIP follows the existing one-to-five ASCII-digit
contract, without padding; all current source ZIPs happened to have five characters.
State is one of the existing 27 Brazilian abbreviations. Missing/invalid mandatory
values fail acceptance while retaining the observation.

Latitude/longitude use double precision and the existing decimal grammar plus native
representability guard. Invalid text, NaN/Infinity extensions, overflow and underflow
become NULL and fail mandatory tests. No decimal rounding or coordinate repair is added.
Global latitude [-90,90] and longitude [-180,180] ranges are blocking domains.
Raw retains original coordinate text; binary floating-point representation is the
accepted coordinate type, not an exact-decimal financial representation.

is_outside_broad_brazil_bounds preserves Phase 2's exploratory latitude [-34,6] and
longitude [-74,-28] warning. Boundaries are inside. The flag is false when either
typed coordinate is missing/rejected; mandatory tests still fail that observation.
It is not a geographic boundary map, business eligibility rule or reason to drop rows.
The later dim_location will provide a unique ZIP domain and coverage/ambiguity metadata.

## Coordinate result transport

The development session reports extra_float_digits=0, which shortens float text output.
Initial native testing exposed a one-case high-precision mismatch; binary fetch and
float8send independently proved the stored binary64 value matches the expected literal.
Native projection checks now use binary result transport and retain strict equality;
no model/helper, coordinate policy or server setting changed. Database-side EXCEPT ALL
compares stored values directly. Before a later API returns precise coordinates, use
binary results or a reviewed positive session output setting; record that read-path gate.
References: [PostgreSQL floating-point output](https://www.postgresql.org/docs/17/datatype-numeric.html#DATATYPE-FLOAT)
and [Psycopg binary results](https://www.psycopg.org/psycopg3/docs/basic/params.html#binary-parameters-and-results).

## Verification and operation

Twelve dbt tests cover mandatory lineage/source/flag values, state accepted values,
composite lineage uniqueness, source domains and complete bidirectional EXCEPT ALL
reconciliation of all fields and flag. There is deliberately no ZIP uniqueness test.
Focused offline/native fixtures exercise duplicates, literal text, missing/rejected
coordinates, global versus exploratory boundaries and count-preserving corruption.
Native PostgreSQL is the authority for double types, planner behavior and EXCEPT ALL;
the offline SQLite adapter does not establish those production database semantics.
Read-only physical checks verify actual session/role, types, counts and API-role denials.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_geolocation
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_geolocation
```

Use [customer staging](customer-staging.md) retained regression instructions and protected
transformer settings. Compatible CREATE OR REPLACE retains view identity/ownership/grants.
View commit precedes tests; failed acceptance is not rollback. Preserve artifacts and
diagnose without drop, full refresh or raw reload. Enable
COMMERCE_WAREHOUSE_GEOLOCATION_INTEGRATION=1 only for the intended read-only modules.

Historical source observations: 1,000,163 observations, 19,015 distinct ZIPs,
261,831 excess exact duplicates and 31 broad-box outliers. These are source-quality
observations, not product metrics or a canonical location policy.

Status: COMPLETE. Focused offline checks 134 passed; Ruff lint/format passed (100
Python files), mypy passed (22 implementation files). Warehouse/API regression 701
passed / 381 deliberate opt-in skips; known AnyIO deprecation warning only. Offline
parse passed. Initial native precision failure was diagnosed as text result transport;
after correction all 72 native cases passed without changing the model/helper.
First/repeat builds each passed one view and all 12 dbt tests; actual-login read-only
physical/access acceptance passed. All 1,000,163 observations, 19,015 ZIPs, 261,831
excess duplicates and 31 warning flags reconcile with source. Repeat view identity,
owner and grants preserved; password absent from retained first/repeat artifacts.
Database 287165587 bytes <400M. See [acceptance evidence](geolocation-staging-verification.json).
Full source/frontend/advisory checks were not rerun for unchanged dependencies/product
code; earlier results remain historical. All nine source staging models are accepted.
Core models and M5 remain; the governance audit waits until verified Phase 3 completion.
