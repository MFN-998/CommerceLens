# Location dimension

Phase 3 M4, following [ADR 0003](decisions/0003-warehouse-contract.md).
Source staging is accepted; this unit introduces the first core dimension.
Current status: COMPLETE, including first/physical/repeat live acceptance.

## Contract and purpose

`core.dim_location` is one row per **literal ZIP prefix** in the union of accepted
customer, seller and geolocation staging views. It includes address ZIPs with no
geolocation evidence. ZIP text keeps its existing one-to-five ASCII digit spelling
and leading zeroes; no padding, trimming, normalization or canonical location policy
is added. Geography is aggregated before joining the unique ZIP domain. Joining every
geolocation observation to a customer/order would multiply records and later amounts.

| Column | Type | Meaning |
| --- | --- | --- |
| zip_code_prefix | text | Unique literal three-source ZIP domain |
| geolocation_observation_count | bigint | All observations, including exact duplicates |
| geolocation_city_variant_count | bigint | Distinct literal geolocation city spellings |
| geolocation_state_variant_count | bigint | Distinct geolocation state values |
| outside_broad_brazil_observation_count | bigint | Retained exploratory broad-box warnings |
| has_geolocation | boolean | Observation count is positive |
| is_geolocation_city_ambiguous | boolean | City variant count exceeds one |
| is_geolocation_state_ambiguous | boolean | State variant count exceeds one |

Literal text grouping uses `COLLATE "C"`, preserving case, accent and whitespace
differences. Counts/ambiguity describe geolocation evidence only, not differences
between customer or seller addresses. Their source geography remains available for
later order-customer/seller models. Uncovered ZIPs receive four zero counters and
three false flags. A city/state/coordinate is never selected as representative.

An invalid or null upstream ZIP is retained and fails validation. It is not silently
filtered from the dimension. Null geolocation city/state/flag inputs also fail, even
among valid observations, since aggregates would otherwise silently ignore them.
Positive observations require positive city/state variant
counts; all counters are nonnegative and no variant/outlier count exceeds observations.

## Acceptance and recovery

Eight not-null tests, one ZIP uniqueness test and three aggregate-only singular tests
cover domains, bidirectional complete multiset reconciliation and address join
conservation. Reconciliation independently groups observation multiplicities before
reconstructing all eight fields; losing duplicates or substituting flags/counts fails.
Join checks compare source **row** counts and uncovered rows, not distinct ZIP counts.

Offline SQL checks use bounded synthetic fixtures in query-only in-memory SQLite;
its adapters do not prove PostgreSQL types/collation/planner semantics. Native checks
execute real model/test SQL through read-only synthetic PostgreSQL CTEs, without
fixture tables or raw records. Physical acceptance checks actual restricted login/TLS,
view ownership/types, exact domain and source totals, row-conserving address joins,
and denied API-role/mart-reader access to core. First/repeat builds must retain view
identity, owner and grants, retain artifacts and remain below the 400 MB guard.

Use the retained [warehouse/API validation workflow](customer-staging.md). New native
and physical checks opt in with `COMMERCE_WAREHOUSE_LOCATION_INTEGRATION=1`; they do
not enable raw-loading or other live tests. Selected commands are:

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select dim_location
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_location
```

Build/test commands connect to the dedicated development transformer configuration.
The non-deleting view materialization uses compatible `CREATE OR REPLACE`; a failed
test is failed acceptance, not database rollback. Preserve the view/artifacts and
diagnose rather than dropping anything. Git checkpoints preserve code; immutable
source, migrations and dbt support reconstruction. No raw reload or migration is needed.

No API/UI, canonical geography, business KPI, dependency, credential or deployment
change belongs to this unit. M5 will measure complete warehouse query plans and recovery;
the comprehensive governance audit waits until all of Phase 3 is verified.

## Verification — 2026-10-03

121 focused offline/runner checks and 59 read-only native PostgreSQL cases passed.
Retained warehouse/API regression: 767 passed / 441 deliberate opt-in skips; known
AnyIO deprecation warning only. Ruff lint/format passed (104 Python files); mypy
passed 22 implementation files. Final offline parse passed. First/repeat each passed
one view/all 12 dbt tests; read-only actual-login physical/access acceptance passed.

19,177 unique ZIPs; all 1,000,163 observations / 31 broad-box flags; 8,556 city-ambiguous
and 8 state-ambiguous ZIPs. Customer/seller joins retain 99,441/3,095 rows and 278/7
uncovered source rows.
Repeat identity/owner/grants preserved; password absent from both artifact trees.
Database 287,173,779 bytes remains below 400 MB. The complete selected
build suites took 78.768/75.849
seconds including tests; these are not individual consumer-query timings. M5 retains
the measured query-plan/performance gate. Initial preflight helper omitted the role
switch; it was corrected before building, without changing database grants.
See [aggregate acceptance evidence](location-dimension-verification.json).
