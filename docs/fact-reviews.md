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

Status: source/offline/native COMPLETE; first/physical/repeat pending.
Scoped source/harness review approved. Candidate offline 59 passed (0.51s);
adopted review/runner 143 passed; warehouse/API 1283 passed with 910
deliberate live skips and the known AnyIO warning. Native read-only 52
passed; actual SQL/calendar roles and configured required macros verified.
A synthetic baseline ID was corrected to valid hex before execution.
Ruff lint/format and mypy (22 implementation files) passed. Offline parse:
`.artifacts/dbt/d71b5d9b05624b4c99e3946101205900`. Preflight confirmed
view absent/parents present, expected source/stage counts and database
287,263,891 bytes; raw reversal comparison remains physical acceptance.
Publish source checkpoint clean before first build. First/physical/repeat:
**Not yet tested**.
Full source/frontend/advisory checks remain historical 2026-09-22 for this
dependency-unchanged unit. E2E/deployment/full governance audit have not run.
Governance follows verified Phase 3 completion, before Phase 4.
