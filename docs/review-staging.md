# Review staging milestone

Phase 3 M4, 2026-10-02. Continues the verified payment staging checkpoint.
Reuse accepted bigint/timestamp helpers; no dependency, migration, raw reload or KPI
change is needed.

## Contract and decisions

Retain all seven source fields and both lineage fields at (review_id, order_id).
Neither review_id nor order_id alone is unique. Preserve every review/order association:
no deduplication, selected review, parent join or row filtering. Literal lowercase
hexadecimal IDs remain text, with a mandatory order reference tested against stg_orders.

Score is an exact signed-64-bit integer with a blocking 1-5 domain. Creation and answer
timestamps use the existing strict canonical/calendar/whole-second source bounds and
remain timestamp without time zone; no timezone conversion or rollover is invented.
Exact empty source text becomes NULL. Missing or rejected mandatory values block
acceptance without dropping the record.

Optional title and message remain literal text, including Unicode, punctuation,
apostrophes, newlines, whitespace and markup. Only the exact empty string becomes NULL;
do not trim, rewrite, truncate or interpret comment contents. These warehouse values
must be treated as untrusted text if later presented by the application; safe rendering
belongs to that future product layer, not destructive source normalization here.

The nonnull is_answer_before_creation flag compares the two valid typed timestamps.
Actual reversals are retained and flagged, not repaired. Missing/rejected dates give
false for this flag and still fail mandatory validation. No duration/eligibility rule.
Multiple-review counts belong to planned core/mart aggregation; 547 historical orders
have multiple reviews. This is an explicit later M4/M5 gate, not a completed staging flag.

## Verification and operation

Fourteen dbt tests cover seven mandatory source/lineage fields, the flag, order reference,
literal numeric score domain, composite grain, lineage uniqueness, domains and full
bidirectional row-multiset reconciliation including optional text and the flag.
Focused fixtures verify literal comment preservation, null versus empty/whitespace,
timestamp reversal/equality, malformed input, repeated individual keys, orphan detection
and count-preserving corruption. Native read-only PostgreSQL cases establish actual
typed behavior; physical access checks verify role permissions, types and independent
source aggregates. Existing exhaustive numeric/timestamp helper tests are reused.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_order_reviews
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_order_reviews
```

Use [customer staging](customer-staging.md) retained regression guidance and restricted
transformer settings. Compatible CREATE OR REPLACE retains the view. View commit
precedes tests; failed acceptance is not rollback. Preserve view/artifacts and diagnose
without drop, full refresh or raw reload. Enable COMMERCE_WAREHOUSE_REVIEW_INTEGRATION=1
only for intended read-only modules; no unrelated empty-target loader fixtures.

Historical source observations: 99,224 rows; 87,656 missing titles; 58,247 missing
messages; zero answers before creation; 547 orders with multiple review records.
These are source reconciliation observations, not customer-satisfaction KPI definitions.

Status: COMPLETE. Ruff lint/format
passed (95 Python files), mypy passed (22 implementation files); offline dbt
parse passed. Warehouse/API regression 620 passed / 308 deliberate opt-in skips,
known AnyIO deprecation warning only. Native read-only review cases 44 passed.
First/repeat builds each passed one view and all 14 dbt tests; actual-login
read-only physical/access acceptance passed. All 99,224 rows and optional comment
contents were retained. Source/view counts match: 87,656 missing titles, 58,247
missing messages, zero reversed answers and 547 orders with multiple reviews.
Repeat view identity/owner/grants preserved; password absent from retained artifacts.
Database 287141011 bytes <400M. See [acceptance evidence](review-staging-verification.json).
Full source/frontend/advisory checks were not rerun for this dependency-unchanged unit;
2026-09-22 results remain historical.
The comprehensive governance audit follows verified Phase 3 completion, before Phase 4.

The private [review fact](fact-reviews.md) is accepted, retaining all ten
fields and adding direct creation/answer calendar roles. M4 is complete;
M5 aggregates review counts without selecting a canonical review.
