# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards, and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M2 COMPLETE; M3 PARTIALLY COMPLETE.
- Current milestone: credential tooling COMPLETE; actual loader provisioning is next.
- Objective: faithfully load all nine sources in one verified, recoverable transaction.
- Status: SAFE TO RESUME. No full source data has been uploaded.

## Completed Work

- Reconciled interrupted session: migration 0002 was applied, with identical replay a no-op.
  Both ledger checksums match Git; nine raw tables and registry were empty on resume.
  API roles have no table access. Published missing implementation/handoff checkpoints.
- Source contracts preserve all 1,550,922 rows, exact decimal totals, framed text hashes,
  empty values, logical row ordinals, and immutable provenance. Migration 0002 adds
  ops.source_loads and nine raw text tables. Prior real migration/COPY fixture test passed.
- Current credential unit adds isolated admin/loader configuration, exclusive durable
  private-file creation, client-side SCRAM verifier generation, refusal to overwrite an
  existing role/file, and explicit recovery when commit acknowledgement is uncertain.
- Existing administrator configuration ACL protected and verified without reading contents.
  Fixed Windows module loading with direct .NET ACL APIs and preserved existing ownership
  so protecting an existing file does not request unnecessary ownership privileges.
- No dependency, source-dataset, or schema changes in this credential unit.

## Files

- Created: src/warehouse/credentials.py, tests/test_warehouse_credentials.py,
  tests/test_warehouse_loader_access_integration.py.
- Modified: src/warehouse/config.py, src/warehouse/__main__.py,
  tests/test_warehouse_config.py, docs/warehouse-development.md, WORK_STATE.md.
- Earlier M3: source.py, 0002_source_landing.sql, source/landing tests, ADR 0004,
  warehouse-load-plan.json and warehouse-storage-estimate.json.
- No deleted/renamed files. Credentials stay ignored and must never be printed.
- Next-unit candidates exist outside Git in the ChatGPT workspace's m3-staging:
  src/warehouse/loading.py, tests/test_warehouse_loading.py and
  tests/test_warehouse_loading_integration.py. They are NOT implemented repository
  features; review/integrate and run tests before use. Ignore unrelated staging copies.

## Technical Decisions

- Dedicated LOGIN commercelens_ingest must be a non-inheriting member only of
  commercelens_loader. No administrator fallback. Loader purpose reads only its
  dedicated ignored configuration file; target and verify-full checks remain mandatory.
- Before writing secrets, private files require owner-only POSIX permissions or Windows
  owner/SYSTEM/Administrators ACL. Existing inherited Windows folder permissions proved
  too broad; protect administrator credentials as well.
- Persist the local credential before committing the database role. Uncertain failures
  retain the file for reconciliation; never silently overwrite, rotate, or delete it.
- All nine COPY operations, registry insertion, full text/count/decimal reconciliation,
  and final capacity check must share one transaction and warehouse advisory lock.
- Free/views decision is unchanged: one snapshot per reviewed target; raw ceiling
  367,000,000 bytes, database ceiling 400,000,000 bytes. Initial models use views.
  ADR 0004 preserves the failed initial 532 MB materialization scenario and approved
  revised 466,728,242-byte budget. Estimates are not guarantees or WAL/disk guarantees.

## Validation

- Resume 2026-09-22: actual PostgreSQL 17.6, verify-full/TLS, schemas/roles unchanged;
  migrations 0001/0002 match, registry/raw empty, API table denials pass.
  Database: 11,234,451 bytes before credential work.
- Full credential checkpoint gate: 140 tests passed, three explicit live tests skipped;
  Ruff lint/format (54 files), mypy (20 source files), package compatibility, frontend
  formatting/lint/types/build, Python/npm advisory and Git-history secret scans passed.
  One existing AnyIO deprecation warning remains. Windows ACL failures were corrected;
  all 19 credential tests passed again after the ownership-preserving fix.
  Actual role provisioning/actual-login permission test: Not yet run.
- Historical source/landing checkpoint: 113 offline tests passed, two live tests skipped;
  real landing rollback test passed separately. Ruff/mypy/packages/frontend gates passed.
- Recovery documentation staged/history secret scans passed; bcd85a9 published.
- Full-size COPY, loader rollback/retry/corruption tests, dbt, and deployment: Not yet tested.

## Current Repository Condition

CLEAN / STABLE at this credential-tooling checkpoint; SAFE TO RESUME for larger M3.
All listed changes are validated and intended for the containing commit. Verify Git status
for final publication. No real loader role has been provisioned; landing remains empty.

## Incomplete Work

- Provision the restricted login, verify permissions
  using that actual login, record evidence, and checkpoint before complete COPY work.
- Integrate/review loading candidate, test interrupted-load rollback, repeat-run identity,
  unchanged-count/money text corruption, provenance changes, and capacity failures.
- Only after those pass: upload all nine sources, reconcile text/rows/exact money/storage,
  rerun idempotently, verify raw hashes unchanged, and checkpoint M3.
- M4 dbt models/M5 queries and populated recovery remain pending. Audit E01–E10 keep
  their documented revisit gates. No model reset credit was redeemed.
- Account usage reached 88% used before live provisioning; preservation mode completed
  the tested credential-tooling unit. Refresh actual usage before the next substantial unit.

## Exact Next Actions

1. Inspect Git status/history and usage; confirm this checkpoint. Check whether
   .env.warehouse.loader and the commercelens_ingest role exist WITHOUT printing credentials.
   Neither was created in this session. Read the provisioning recovery guide if either exists.
2. If both are absent, run provision-loader, then the actual-login access test below.
   Record its outcome and checkpoint before integrating complete COPY work.
3. Integrate and test the three loading candidates; implement a loader-purpose CLI
   that prepares source before connecting and prints success only after commit.
4. Checkpoint validated code, execute full load/retry, record actual evidence, then start M4.

## Git State

- Branch feat/warehouse-foundation; main is unchanged/unmerged.
- Published pre-risk baseline bcd85a9; source/capacity b6acd5b; landing schema 625dbe8.
- Credential implementation is the containing commit; staged/history scans precede push.
- M2 implementation aa0104f; final foundation evidence 207b74f.
- The commit containing this handoff is the current checkpoint when committed;
  resolve with git log below. Confirm status/publication instead of assuming them.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
git log -1 --format="%H %s" -- WORK_STATE.md
uv run --locked --group warehouse python -m src.warehouse inspect
uv run --locked --group warehouse pytest tests/test_warehouse_config.py tests/test_warehouse_credentials.py
./scripts/check.ps1 -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
# Only once, after validated code checkpoint; never overwrite existing credentials:
uv run --locked --group warehouse python -m src.warehouse provision-loader
$env:COMMERCE_WAREHOUSE_LOADER_ACCESS_INTEGRATION = '1'
try { uv run --locked --group warehouse pytest tests/test_warehouse_loader_access_integration.py }
finally { Remove-Item Env:\COMMERCE_WAREHOUSE_LOADER_ACCESS_INTEGRATION }
```

Never print `.env.warehouse`, `.env.warehouse.loader`, or credentials.
