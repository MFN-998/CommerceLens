# Date dimension

Phase 3 M4, under [ADR 0003](decisions/0003-warehouse-contract.md).
Status: COMPLETE; first/physical/repeat acceptance verified 2026-10-04.

`core.dim_date` is a private view at one **observed calendar date**, drawn from
all five order timestamps, item shipping deadlines, and both review timestamps.
Source timestamps have no declared timezone; conversion to `date` uses the
accepted `timestamp without time zone` value without inventing a timezone.

The nine fields are `calendar_date` (`date`), seven integer attributes
(`calendar_year`, `calendar_quarter`, `calendar_month`, `day_of_month`,
`iso_year`, `iso_week`, `iso_day_of_week`) and boolean `is_weekend`.
ISO weekdays run from Monday 1 to Sunday 7. ISO year/week may differ from
calendar year at New Year; weekend means ISO weekday 6 or 7.

Duplicate source event dates collapse at the declared calendar-date grain.
Missing optional events contribute no date. No order-status, event-order,
shipping-warning or business-eligibility filter is applied. Malformed nonempty
source timestamp parsing remains a blocking upstream staging responsibility;
omitting optional NULL events does not authorize ignoring failed staging tests.
All original timestamps and quality flags remain available for later facts.

This is an observed-date domain, not a generated continuous calendar. Dates with
no retained event are absent. Consumers needing gap-filled forecasting periods
must define their series/calendar policy in the appropriate later phase.
There is no surrogate key, current-date dependency, localized label, KPI,
duration or repaired date.

Read-only preflight on 2026-10-04 found 803,395 nonnull events and 755 dates
from 2016-09-04 to 2020-04-09. Later warning dates remain included. These are
snapshot evidence, not hard-coded production validity bounds.

Required/unique tests protect the grain. A singular domain check verifies all
calendar/ISO/weekend attributes, including NULL consistency. Full bidirectional
`EXCEPT ALL` reconciliation detects missing, extra, duplicated or changed dates
and attributes. The domain test materializes the nine-field date input before
checking its attributes, preventing predicate pushdown into all source events;
the same NULL-safe assertions remain. This local validation boundary addresses
the measured 35.32-second consistency node in the first build, not consumer
query performance. Offline synthetic fixtures exercise actual SQL and configured
generic macros with a small documented SQLite date-syntax adapter. Native
read-only PostgreSQL fixtures independently verify Python calendar/ISO
expectations. Physical acceptance compares all nine fields to staging, checks
the eight raw-to-staging event fields with lineage, expected types/ownership,
actual restricted login/TLS and denied API/reader access; diagnostics are
metadata and aggregates only.

Use [retained warehouse/API validation](customer-staging.md). Live tests opt in
only with `COMMERCE_WAREHOUSE_DATE_DIMENSION_INTEGRATION=1`.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select dim_date
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select dim_date
```

Publish verified code before first build. Compatible `CREATE OR REPLACE` retains
view identity/owner/grants, but commits before tests: failed acceptance is not
automatic rollback. Preserve the relation/artifacts and diagnose. Build this new
child before eager parent tests which now reference it. Private schemas,
restricted roles, verified TLS and Free/views-first storage remain unchanged.

No source reload, migration, dependency, credential, API/UI, deployment or
resource deletion is required. Measured consumer-query performance and full
warehouse reconstruction remain M5; comprehensive governance follows verified
Phase 3 completion and precedes Phase 4.

## Verification — 2026-10-04

35 candidate offline cases passed. Initial collection was sandbox-blocked;
confined collection/escalation resolved it before any implementation or database
failure. Adopted focused tests: 100 passed. Warehouse/API regression: 921 passed,
594 deliberately opted-out live cases, known AnyIO warning only. Native PostgreSQL
read-only suite: 38 passed, including typed empty results and timezone independence.
Ruff lint/format passed (120 Python files); mypy passed 22 implementation files;
offline dbt parse passed. Scoped independent review approved.
First live build passed one view/all 12 tests in 107.963 seconds. Physical/access
passed separately (one case). The reviewed consistency boundary subsequently
passed all 35 offline/38 native cases and a fresh offline parse. Compatible
repeat passed all 12 dbt tests in 76.572 seconds, preserving view
identity/owner/grants. All eight raw/staged clocks including NULLs and lineage
matched (808,303 event positions, 803,395 nonnull events); all 755 dates/nine
fields/types/private denials verified. Password absent from both artifacts.
Database 287,222,931 bytes <400 MB.
See [aggregate evidence](date-dimension-verification.json). Measured suite
timing includes tests, not API latency; consumer-query performance/recovery remains M5.

Next core unit after acceptance: `int_order_customers`, preserving each
order-linked source customer record and address under ADR 0003.
