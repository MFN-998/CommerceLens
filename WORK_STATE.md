# CommerceLens work state

Updated: 2026-09-27. Repository: `D:\My Projects\CommerceLens`.
Read AGENTS, master plan, engineering standards, execution protocol and deletion-and-governance.

## Project State

- Phases 1–2/audit and Phase 3 M1–M3 COMPLETE. M4 IN PROGRESS; M5 pending.
- Current milestone: customer staging COMPLETE at 1785472; seller staging IN PROGRESS.
- Current task: verify/checkpoint prepared seller SQL and tests, then selected live acceptance.
- Objective remains the tested analytical warehouse. No Phase 4 work or exit audit yet.
- Allowance reset at start (97% five-hour / 100% weekly). Last observed 12% five-hour / 86%
  weekly before final verification; preserve this completed unit rather than start another.

## Completed Work

- Resumed clean 142277c; verified live Supabase/dbt setup was already complete.
- Recorded permanent deletion approval rule and post-Phase-3/pre-Phase-4 governance gate.
- Added stg_customers, explicit null handling, source/lineage reconciliation and data tests.
- Added narrowly selected dbt build/test with result validation; retained per-run artifacts.
- Added non-deleting Postgres CREATE OR REPLACE view materialization and retained pytest fixture.
- Built and rebuilt the customer view; live data/identity/access checks passed.

## Files

- Created: docs/deletion-and-governance.md, docs/customer-staging.md,
  docs/customer-staging-verification.json, conftest.py, dbt/macros/materializations/view.sql,
  dbt/models/staging/stg_customers.sql/yml, three dbt/tests/stg_customers_*.sql files,
  tests/test_warehouse_customer_staging.py and test_warehouse_customer_integration.py.
- Modified: AGENTS.md, master plan, engineering standards, phase-3 plan, dbt-development,
  CONTRIBUTING, WORK_STATE, dbt_project.yml, warehouse CLI/runner and CLI/dbt tests.
- During implementation tests/conftest.py moved to root conftest.py to cover API tests;
  neither path was previously tracked. No files/resources deleted. Artifacts retained/ignored.
- No dependencies, applied migrations, source data or protected credentials changed.

## Technical Decisions

- Preserve one row per customer_id; cross-order customer_unique_id may repeat. Preserve
  literal ZIP/IDs/text/lineage; exact empty text becomes NULL. Fail invalid data without removal.
- Keep views on Free; raw/database ceilings 367M/400M bytes; no new materialized data copies.
- Override only Postgres view materialization: CREATE OR REPLACE preserves object identity,
  ownership/grants/dependents; incompatible columns or non-view replacement fail. No hooks,
  SQL header or grant overrides. Failed data tests preserve the committed view for diagnosis.
- Build/test requires exactly approved stg_customers; no arbitrary selectors/full-refresh.
  Verify expected model/test results, rejecting empty successful selections. Transformer only.
- Classic parser, test failure storage off, test schema staging, fresh retained artifact dirs.
- Custom tmp_path uses UUID mkdir; targeted pytest uses capture=sys, no cache/autoload plugins.
  Existing full check.ps1 includes source fixture and frontend deletion: do not run unapproved.

## Validation

- Ruff lint/format passed (69 Python files); mypy passed (22 implementation files).
- 47 focused offline checks passed, including real guarded parse/debug and SQL fixtures.
- Warehouse/API regression: 168 passed / 14 opt-in live tests skipped; known AnyIO warning.
- Initial option/schema errors and API temp-fixture scope error resolved before acceptance.
- First and repeat live dbt builds: one view plus 12 data tests passed each. Full source
  field/lineage multiset reconciliation passed; raw/staging both 99,441 customer rows.
- Separate live read-only customer integration test passed: physical types, owner, counts,
  API denial and no swap relations. Repeat retained same relation OID/owner/grants.
- Database 287,059,091 bytes; no password in repeat artifacts. See JSON evidence.
- Full source/frontend/advisory gate not rerun: cleanup requires approval/adaptation and no
  affected frontend/dependency changes. Historical full gate 2026-09-22 remains documented.
- M3 historical evidence: all nine raw tables / 1,550,922 rows and idempotent replay verified.
- No model training, E2E/deployment or full governance audit performed.

## Current Repository Condition

PARTIALLY IMPLEMENTED seller unit; customer baseline remains verified at 1785472.
Seller files/selector are saved but not yet repository/live verified. SAFE TO RESUME.
Do not delete artifacts, rerun empty-target fixtures, reprovision accounts or reload raw data.

## Incomplete Work

- Remaining eight staging models, core dimensions/facts and their data tests; then M5 marts,
  technical queries, performance and reconstruction checks. Customer-only unit is complete.
- Any full source/frontend gate needs specifically approved deletion or a reviewed retained
  workflow. No blanket cleanup approval exists. No known current failing customer check.
- Audit E01–E10 retain their revisit gates. Comprehensive governance audit is required only
  after all Phase 3 functionality passes; fix Critical/relevant Important issues before Phase 4.

## Exact Next Actions

1. Check usage/status/history; read docs/customer-staging.md and ADR 0003. Do not repeat
   customer implementation or account setup. Verify metadata only if needed after a gap.
2. Choose the next small staging source (sellers is a similar literal-text contract), inspect
   its Phase 2 rules/observations, add SQL/YAML/reconciliation/synthetic tests and update the
   approved selector intentionally. Preserve the no-delete materialization and private profile.
3. Run retained relevant checks, then selected build/data/access and repeat verification.
   Record evidence and checkpoint before wider staging/core work.
4. Finish M4/M5, then run the required governance audit; Phase 4 cannot start before that gate.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Live setup 142277c; governance 47e35a7; customer implementation 193be34.
- This final acceptance is the containing commit; resolve with
  git log -1 --format="%H %s" -- WORK_STATE.md.
- Scan staged export and post-commit history; publish feature branch and verify clean status.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_customers
```

Use docs/customer-staging.md for retained regression/build commands. Do not automatically
run the older cleanup-based full gate. Never print credentials, raw records or driver errors.

Active resume: clean published 1785472; customer milestone fully complete, no partial edits.
Allowance at resume 99% five-hour / 84% weekly. Next unit is stg_sellers using the existing
contract/view/test approach. Owner clarified project-file permission vs legitimate product
data deletion; recorded in AGENTS and governance. Reviewing six obsolete dbt scan exports
for an explicit cleanup proposal; no deletion approved/performed. Customer read-only check
and seller candidate validation pending. No phase restart, account setup or redesign needed.

Owner approved removal of exactly six dbt tooling/bootstrap/handoff checkpoint export folders/ZIPs. Removed them after path and reparse-point checks; verified absence and unchanged Git status. No other cleanup authorized. Customer read-only resume check passed.

Seller implementation prepared: seven model/test files, approved selector and parameterized
runner regression; seller guide added and customer guide linked. No live seller build yet.
Next: retained Ruff/mypy/warehouse/API checks, review/secret scan and code checkpoint;
then selected seller build, read-only acceptance and repeat identity/access verification.
Latest allowance: 46% five-hour / 76% weekly. Category candidate is scratch-only, not integrated.

Seller repository validation passed: Ruff lint/format (72 files), mypy (22 files), warehouse/API 175 passed, 16 deliberately skipped; historical AnyIO warning only. Live seller build/acceptance still pending. Reviewed diff; checkpoint before live creation. Staged complete file contents will be secret-scanned in memory, avoiding new scan export copies.
