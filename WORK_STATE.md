# CommerceLens work state

Updated: 2026-09-27. Repository: `D:\My Projects\CommerceLens`.
Read AGENTS, master plan, engineering standards, execution protocol and deletion-and-governance.

## Project State

- Phases 1–2 and their audit COMPLETE. Phase 3 M1–M3 COMPLETE; M4 IN PROGRESS; M5 pending.
- Current milestone: customer and seller staging COMPLETE / SAFE TO RESUME.
- Current task: checkpoint seller acceptance, then category translation staging.
- Overall objective: tested analytical warehouse; no Phase 4 work or comprehensive exit audit yet.
- Latest allowance observation: 46% five-hour / 76% weekly; recheck before another major unit.

## Completed Work

- Recovered clean published 1785472; no interrupted code edits. Customer read-only recheck passed.
- Added seller projection, 11 dbt data tests, synthetic and read-only live tests, narrow selector.
- Parameterized selected-runner regression across approved models. Retained existing view/profile design.
- First/repeat seller builds passed; counts, reconciliation, ownership, types and API denials verified.
- Persisted project-file vs product-data deletion distinction and ongoing cleanliness obligations.
- Specifically approved obsolete scan copies removed after resolved-path/reparse checks; Git status
  unchanged by cleanup: .artifacts/dbt-{tooling,bootstrap,handoff}-checkpoint-export folders
  and .artifacts/dbt-{tooling,bootstrap,handoff}-checkpoint.zip files. No other deletion authorized.

## Files

- Added seller SQL/YAML, three dbt/tests/stg_sellers_*.sql, two tests/test_warehouse_seller_*.py,
  docs/seller-staging.md and docs/seller-staging-verification.json.
- Modified src/warehouse/dbt_runner.py, tests/test_warehouse_dbt.py, customer guide, phase-3 plan,
  AGENTS.md, docs/deletion-and-governance.md and this handoff.
- No tracked files deleted/renamed. No dependencies, migrations, source data or credentials changed.
- Category candidate exists only in the chat scratch directory m4-category-candidate-20260927;
  it is not integrated or live verified. Read its README and review before adoption.

## Technical Decisions

- Preserve source grain, keys/ZIP/text and lineage. Exact empty text becomes NULL; invalid and
  duplicate rows fail tests without removal. Seven seller geography gaps remain warnings.
- Free plan, views-first. Raw/database ceilings 367M/400M bytes. No materialized data copies.
- Existing CREATE OR REPLACE view materialization preserves identity/owner/grants/dependents;
  incompatible schema replacement fails. Data tests follow view commit; failure is not rollback.
- Only stg_customers/stg_sellers approved; transformer credentials and verify-full TLS only.
- Retain UUID dbt/pytest artifacts, no file logs/telemetry/failure row storage. Existing full
  check.ps1 includes cleanup that needs specific permission or reviewed retained alternatives.
- Scan complete staged changed files in memory with Gitleaks stdin; no new scan export archives.

## Validation

- Seller unit: Ruff lint/format passed (72 files), mypy passed (22 implementation files).
- Warehouse/API regression: 175 passed, 16 deliberately skipped, known AnyIO deprecation warning.
- First/repeat seller dbt builds: one view plus 11 tests passed each. Full multiset reconciliation
  passed; both raw/staging retain 3,095 rows. Separate read-only seller integration test passed.
- Repeat preserved OID/owner/grants; no transformer password found in repeat artifacts.
- See seller JSON for measured storage and exact test statuses. Customer prior evidence: 99,441
  rows, 12 tests and repeat acceptance. M3: nine raw tables, 1,550,922 rows; no reload needed.
- Complete staged implementation contents secret scan passed before 7cc622f. Final docs/history
  scan and publication pending this checkpoint. Do not claim advisory/full UI gate rerun.
- Source/frontend/dependency gate was last run 2026-09-22; unchanged here and not rerun.
- No deployment, E2E or comprehensive post-Phase-3 audit performed.

## Current Repository Condition

CLEAN / STABLE implementation at 7cc622f; seller acceptance documentation/evidence pending
the containing checkpoint at writing. SAFE TO RESUME. No known failing seller check.

## Incomplete Work

- Seven remaining staging models, core dimensions/facts and tests; M5 marts/technical queries,
  performance and reconstruction checks. Category translation is the next small unit.
- Existing full check.ps1 cleanup requires permission/adaptation. Do not run empty-target
  live loading fixtures against the populated warehouse or reprovision accounts.
- Audit E01–E10 keep their revisit gates. Full governance audit only after all Phase 3 passes;
  fix Critical/relevant Important issues and verify Phases 1–3 before Phase 4.

## Exact Next Actions

1. Inspect usage/status/history and seller acceptance evidence. Finish final scan/checkpoint
   and publication if not already in Git; do not repeat customer/seller implementation.
2. Review m4-category-candidate-20260927 in this chat scratch directory, the source contract
   and ADR 0003. Adopt only its seven model/test files; expand the approved selector.
3. Run retained regression/parse/style/type checks, code checkpoint, selected live category
   build and read-only acceptance/repeat checks. Record evidence and checkpoint.
4. Continue remaining M4/M5 units, then required governance gate before Phase 4.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Customer acceptance 1785472; seller implementation 7cc622f.
- Final acceptance is the containing commit: git log -1 --format="%H %s" -- WORK_STATE.md.
- Scan staged contents/history, push feature branch and confirm clean status after commit.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
.venv/Scripts/python.exe -B -m src.warehouse dbt-parse
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_sellers
```

Use docs/customer-staging.md for retained regression commands and docs/seller-staging.md
for seller operation. No automatic cleanup; never print credentials, raw rows or driver errors.
