# CommerceLens work state

Updated: 2026-10-01. Repository: `D:\My Projects\CommerceLens`.
Read AGENTS, master plan, engineering standards, execution protocol and deletion-and-governance.

## Project State

- Phases 1–2 and their audit COMPLETE. Phase 3 M1–M3 COMPLETE; M4 IN PROGRESS; M5 pending.
- Current milestone: customer, seller and category translation staging COMPLETE / SAFE TO RESUME.
- Current task: products staging prepared; offline and native synthetic validation before checkpoint/live build.
- Overall objective: tested analytical warehouse; no Phase 4 work or comprehensive exit audit yet.
- Usage is constrained; finish this checkpoint and stop before another implementation unit.
  Latest observation: 15% five-hour / 71% weekly remaining. Recheck before resuming.

## Completed Work

- Recovered clean published 1785472; no interrupted code edits. Customer read-only recheck passed.
- Added seller projection, 11 dbt data tests, synthetic and read-only live tests, narrow selector.
- Parameterized selected-runner regression across approved models. Retained existing view/profile design.
- First/repeat seller and category builds passed; counts/reconciliation/types/ownership/API denials verified.
- Added category projection, eight dbt tests, five synthetic tests and actual-login read-only acceptance.
- Persisted project-file vs product-data deletion distinction and ongoing cleanliness obligations.
- Specifically approved obsolete scan copies removed after resolved-path/reparse checks; Git status
  unchanged by cleanup: .artifacts/dbt-{tooling,bootstrap,handoff}-checkpoint-export folders
  and .artifacts/dbt-{tooling,bootstrap,handoff}-checkpoint.zip files. No other deletion authorized.

## Files

- Added seller SQL/YAML, three dbt/tests/stg_sellers_*.sql, two tests/test_warehouse_seller_*.py,
  docs/seller-staging.md and docs/seller-staging-verification.json.
- Added category SQL/YAML, three matching dbt tests, two category Python tests, guide and JSON evidence.
- Modified src/warehouse/dbt_runner.py, tests/test_warehouse_dbt.py, customer guide, phase-3 plan,
  AGENTS.md, docs/deletion-and-governance.md and this handoff.
- No tracked files deleted/renamed. No dependencies, migrations, source data or credentials changed.
- Seller/category scratch candidates were adopted and verified; they remain outside the repo,
  retained without deletion. Do not re-adopt them or treat them as active implementations.

## Technical Decisions

- Preserve source grain, keys/ZIP/text and lineage. Exact empty text becomes NULL; invalid and
  duplicate rows fail tests without removal. Seven seller geography gaps remain warnings.
- Free plan, views-first. Raw/database ceilings 367M/400M bytes. No materialized data copies.
- Existing CREATE OR REPLACE view materialization preserves identity/owner/grants/dependents;
  incompatible schema replacement fails. Data tests follow view commit; failure is not rollback.
- Only stg_customers/stg_sellers/stg_category_translation approved; transformer and verify-full TLS only.
- Portuguese category is the unique key; English translations may repeat. Preserve missing
  translation coverage warnings; no category/product filter or invented labels.
- Retain UUID dbt/pytest artifacts, no file logs/telemetry/failure row storage. Existing full
  check.ps1 includes cleanup that needs specific permission or reviewed retained alternatives.
- Scan complete staged changed files in memory with Gitleaks stdin; no new scan export archives.

## Validation

- Final Ruff lint/format passed (75 files); mypy passed (22 implementation files).
- Warehouse/API regression: 182 passed, 17 deliberately skipped; known AnyIO deprecation warning.
- Real guarded offline dbt parse and selected-runner tests passed for the expanded project.
- Seller first/repeat builds: 11 tests each, 3,095 rows; category: eight tests each, 71 rows.
  Full multiset reconciliation passed. Separate live read-only tests passed for both models.
- Repeat OID/owner/grants preserved and passwords absent from repeat artifacts. Aggregate
  evidence in seller/category JSON files; storage below 400M bytes. No raw reload.
- Customer read-only resume check passed. Its prior build evidence retains 99,441 rows/12 tests.
- M3 acceptance remains nine tables/1,550,922 rows. Do not rerun destructive empty-target fixtures.
- Complete staged implementation secret scans passed; seller history scan/publication passed.
  Final acceptance also requires staged-content and history scanning before publication.
- Full source/frontend/advisory gate not rerun; last historical pass 2026-09-22. No dependency
  changes, deployment, E2E or comprehensive post-Phase-3 audit this session.

## Current Repository Condition

STABLE / SAFE TO RESUME. Implementation e9b1da6 and the containing acceptance checkpoint
record both completed units. No known failing current checks. Verify actual Git cleanliness
and publication on resume; no remaining partial model implementation.

## Incomplete Work

- Six staging sources remain: products, orders, order_items, order_payments, order_reviews,
  geolocation. Then core dimensions/facts/tests, M5 marts/technical queries, performance and
  reconstruction checks. Products staging is the next unit; it has nullable typed attributes.
- Existing full check.ps1 cleanup requires permission/adaptation. Do not run empty-target
  live loading fixtures against the populated warehouse or reprovision accounts.
- Audit E01–E10 keep their revisit gates. Full governance audit only after all Phase 3 passes;
  fix Critical/relevant Important issues and verify Phases 1–3 before Phase 4.

## Exact Next Actions

1. Check allowance, git status and recent history; read category/seller evidence and compare
   with this handoff. Confirm the containing acceptance commit is published and the tree clean.
2. Read src/validation/contracts.py TABLES["products"], docs/data-quality-report.md product
   warnings and ADR 0003. Implement stg_products with nullable typed attributes and explicit
   quality flags; preserve missing categories, missing dimensions and zero weight as specified.
3. Add source/lineage/domain/reconciliation and meaningful synthetic tests, extend the narrow
   selector, run retained checks, checkpoint, then live build/access/repeat acceptance.
4. Continue remaining M4/M5 units, then required governance gate before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Customer acceptance 1785472; seller implementation 7cc622f/acceptance 304bf75.
- Category implementation e9b1da6; final acceptance is the containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
- Scan staged contents/history, push feature branch and confirm clean status after commit.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_category_translation
```

Use docs/customer-staging.md for retained regression commands and docs/seller-staging.md
and docs/category-translation-staging.md for selected model operation. No automatic cleanup; never print credentials, raw rows or driver errors.

Resume 2026-10-01: verified clean published b7ec0bb, no partially completed edits. Customer/seller/category staging complete. Current allowance 99% five-hour / 55% weekly. Next atomic unit is stg_products with typed nullable attributes and explicit quality flags. Read-only existing-view recheck pending; product candidate is scratch-only until review.

Read-only customer/seller/category resume integration recheck passed: 3 tests. Existing baseline reconciled; no raw reload or model rebuild. Product implementation pending review.

Products unit adopted: source_numeric macros, SQL/YAML, three dbt tests, synthetic/physical/
native read-only Python tests and product guide. Narrow selector includes only stg_products
additionally. No dependency/migration/data/credential changes or deletion. Validation not yet
run on adopted files; no product view built. Current unit PARTIALLY IMPLEMENTED / SAFE TO RESUME.
Next: retained style/type/regression and opt-in read-only native synthetic tests, code checkpoint;
then selected live build, physical acceptance and repeat identity/flag/storage verification.

Product validation: Ruff lint/format (79 files), mypy (22), warehouse/API regression 241 passed / 48 deliberate skips. Native synthetic run: 6 passed / 24 failures; first failure extreme exponent, remaining tests shared aborted transaction. No product view built. Resolve guarded parser and isolate cases before code checkpoint/live build.

Native probe confirmed validity functions return false safely. Initial error was planner folding immutable casts in inline VALUES, not validator failure. Hardened helpers cast guarded text first; native fixture uses table-like MATERIALIZED input and per-case savepoints. Rerun repository gates and 31 native cases passed, including inline-constant regression. No product view built yet.
