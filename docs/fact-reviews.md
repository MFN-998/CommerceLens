# Review fact milestone

Phase 3 M4, 2026-10-04. Continues verified payment acceptance 2829ce2.
Private core view; no dependency, migration or source reload.

## Contract and decisions

Retain every (review_id, order_id) pair and all ten accepted staging fields.
Neither identifier alone is unique. Literal nullable title/message, immutable
lineage, integral score, source events and answer-before-creation warning remain
unchanged. Optional text is untrusted if a future application displays it; safe
rendering belongs at that product boundary, not destructive normalization here.

Two direct calendar dates link creation and answer events to accepted dim_date.
Source timestamps have no declared timezone; casting timestamp without time zone
to date introduces no timezone policy. Required order/date membership is tested
separately. There are no joins, filters, aggregations, selected reviews, repaired
events, durations or eligibility rules. Missing required input remains visible
and blocks acceptance. Independent M5 child aggregation will report multiple-review
counts; it must retain the 547 historical orders with multiple reviews.

## Verification and operation

Ten required-field checks exclude optional title/message. Four singular checks
cover composite grain, domains/flag/date correspondence, full twelve-field
bidirectional multiset conservation and required order/calendar membership.
Synthetic tests exercise actual SQL and configured null macros; physical
acceptance independently checks raw/staging/core content using aggregate-only
diagnostics, native types, lineage, retained warnings/text and private access.

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select fact_reviews
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select fact_reviews
```

Use [customer staging](customer-staging.md) for retained checks and restricted
transformer settings. Enable COMMERCE_WAREHOUSE_FACT_REVIEWS_INTEGRATION=1 only
for intended read-only modules. Never enable empty-target loader fixtures against
the populated warehouse. Compatible CREATE OR REPLACE retains the view; commit
precedes tests. Failed acceptance is not rollback: preserve view/artifacts and
diagnose without drop, full refresh, source reload or unapproved resource deletion.

Historical source: 99,224 pairs, 87,656 missing titles, 58,247 missing messages,
zero reversed answers and 547 orders with multiple reviews. These source
observations are not satisfaction metrics or a selected-review policy.

Status: COMPLETE. Candidate offline 59, adopted review/runner 143,
warehouse/API 1283 (910 deliberate live skips), native read-only PostgreSQL 52
and physical/access 2 tests passed. Ruff lint/format 140 reported files, mypy 22
implementation files and offline parse passed. Known AnyIO warning only.
Source 23101c2 published clean before first build. First/repeat each passed
one view/all 14 dbt tests in 65.287/68.7 seconds. All 99,224 pairs, literal
optional comments, lineage/events/score/reversal warning and both direct
calendar roles conserved. Missing titles/messages 87,656/58,247, reversals 0
and multiple-review orders 547 match independently guarded raw/staging/core
multisets and aggregates. Native metadata, timestamp bounds, required order/
date memberships and restricted actual login/role/verify-full TLS/private
API/reader denials passed. Repeat preserved view identity/owner/grants;
password absent from first/repeat artifacts. Database 287,288,467 bytes <400M.
See [aggregate evidence](fact-reviews-verification.json) for nodes/artifact paths.
Suite timings are not consumer latency; M5 measured plans/recovery remain.

M4 is complete; M5 mart/examples/performance/reconstruction remain. Full
source/frontend/advisory gate remains historical 2026-09-22 for unchanged
dependencies; E2E/deployment/full governance audit not run. The required audit
follows verified Phase 3 completion, before Phase 4. No project resource deleted.
