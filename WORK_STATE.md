# CommerceLens work state

Updated: 2026-09-21. Repository: `D:\My Projects\CommerceLens`.
Read with root instructions, master plan, engineering standards, and execution protocol.

## Project State

- Phases 1–2 and engineering audit COMPLETE. Phase 3 PARTIALLY COMPLETE.
- M1 design COMPLETE. M2 database foundation COMPLETE and applied; Phase 3 M3 is next.
- Current task: M2 completed; next unit is storage sizing and reproducible source loading.
- Objective: tested private analytical warehouse within the master-plan phase boundaries.
- Status: **M2 COMPLETE / SAFE TO RESUME Phase 3**. Five private schemas and four restricted
  roles are persistent; no source records loaded.

## Completed Work

- Reconciled clean published checkpoint `3e96ef9`; preserved completed Phases 1–2.
- Verified owner-created Supabase **CommerceLens**, ref `imvahwzlovgmaltuysmb`, Tokyo
  (`ap-northeast-1`), Free/Nano. Keep this project; do not rename or create a duplicate.
- Verified PostgreSQL 17.6, direct IPv6, certificate-verified encrypted authentication.
- Added separate pinned warehouse driver group, guarded configuration, migration runner,
  private-schema/capability-role SQL, transactional privilege checks, and recovery tests.
- Real rehearsal exercised creation, permitted/denied operations, unchanged migration replay,
  and complete rollback. Integration test also proved checksum rejection, injected DDL failure
  with no surviving object/ledger row, concurrent-run lock protection, and fresh-session rebuild.
- Applied migration 0001 after code checkpoint `aa0104f`; unchanged replay returned no migrations.
  Post-apply privilege checks passed and removed all test objects. Dashboard confirmed
  2 of 7 schemas exposed and 0 of 1 tables exposed; warehouse schemas remain private.
- Owner privately populated ignored `.env.warehouse`; never display or commit its contents.

## Files

- Created: `.env.warehouse.example`, `src/warehouse/` (configuration, runner, CLI),
  `warehouse/migrations/0001_foundation.sql`, `warehouse/checks/privileges.sql`,
  three `tests/test_warehouse_*.py` files, `docs/warehouse-development.md`.
- Modified: `pyproject.toml`, `uv.lock`, `scripts/check.ps1`, `CONTRIBUTING.md`,
  `README.md`, `docs/phase-3-plan.md`, `WORK_STATE.md`.
- Local ignored: `.env.warehouse`, `.credentials/supabase-ca.crt`; contain local configuration.
- Deleted/renamed: none. Source CSV/Parquet and application behavior unchanged.

## Technical Decisions

- Psycopg binary 3.3.6 (libpq 18.4) is isolated in the optional warehouse group; exact lockfile.
- Direct target works; no session-pooler or paid IPv4 add-on needed. Always `verify-full`.
  The public CA comes from the dashboard; no TLS fallback/disabled certificate checks.
- Four restricted NOLOGIN capabilities; owner owns ops/raw, transformer owns staging/core/marts.
  Loader can read/insert raw; reader only explicitly approved marts. API roles have no access.
- Apply SQL as intended creator roles; defaults protect future tables/functions/types/sequences.
- Ordered LF-normalized SHA-256 migration ledger and whole-batch transactions under a lock.
  History drift fails rather than silently repairing it; never edit an applied migration.
- Bootstrap uses the existing administrator. M3/M4 must add least-privilege job credentials
  before routine loading/transformation. No administrator credential reaches the frontend.
- Free-plan 500 MB allowance is a gate before M3: estimate landing/index/build/materialization
  space. Do not silently upgrade, omit source rows, or redefine project scope to fit.

## Validation

- Actual connection: PostgreSQL 17.6, TLS in use with `verify-full`; empty warehouse confirmed.
- Bootstrap rehearsal passed; fixtures rolled back. Opt-in real integration test: 1 passed,
  including failure rollback, checksum drift, lock contention, and fresh-session reconstruction.
- Offline suite: 86 passed, 1 real-database test intentionally skipped; that test passed separately.
- Ruff lint/format and mypy (18 source files) passed; 72 installed packages compatible.
- Full gate passed: frontend Prettier/ESLint/TypeScript/build, Python dependency audit,
  npm audit, and Git history secret scan. No known advisories/leaks found.
- Initial port parsing issue was corrected and covered by a dedicated environment-file test.
- Initial generic Python TLS probe rejected the CA under Python's strict extension rules;
  the actual libpq client passed full chain/hostname verification. See warehouse guide.
- Historical Phase 2: nine raw files/staging hashes verified, zero blocking errors, 29 warnings.
  No data pipeline regeneration required for this unit.
- No populated warehouse, dbt, full data reconstruction, or deployment validation yet.

## Current Repository Condition

**CLEAN / STABLE — verified M2 database foundation.** Code is committed at `aa0104f`.
The final checkpoint contains only the three updated handoff/phase/setup documents;
confirm the live working tree after that commit. Migration 0001 is persistent, replay is
a no-op, and all verification fixtures were removed. Existing app remains functional.

## Incomplete Work

- No outstanding M2 implementation failure. Data API exposes only public/graphql_public;
  creator-specific defaults and tested privileges keep warehouse objects inaccessible to API roles.
  Preserve/recheck this boundary when adding loaders, dbt models, or new login memberships.
- M3–M5: storage sizing, source landing/provenance/idempotent loading, least-privilege jobs,
  dbt dimensions/facts/tests, technical marts/query grain checks, populated reconstruction.
- Bootstrap reconstruction used empty-target rollback/fresh-session rebuild. It is not a
  populated backup/restore test. Review server-side SSL enforcement/network allowlists before deployment.
- Audit E01–E10 remain with existing revisit gates; known AnyIO deprecation persists.
- Latest account usage observed: 94% used / 6% remaining; preservation mode selected.
  Refresh before M3. No reset credit redeemed; no additional large unit started.

## Exact Next Actions

1. Read this handoff and warehouse guide; inspect Git status/history, refresh usage, and run
   `uv run --locked --group warehouse python -m src.warehouse inspect` to reconcile live state.
2. Start M3 by measuring expected landing/index/build/materialization storage against the
   500 MB allowance. Preserve all nine source tables and documented grains; resolve capacity
   before loading. Do not silently buy upgrades or reduce source coverage.
3. Implement narrowly scoped loader credentials/membership, versioned source landing and
   load registry, exact decimal reconciliation, atomic load and idempotent retry tests.
4. Checkpoint M3 before dbt M4. Follow master-plan acceptance gates; do not redo Phases 1–2.

## Git State

- Branch: `feat/warehouse-foundation`; starting clean published checkpoint
  `3e96ef9ac73292de6c33042a13b460b7a48164db`.
- Protocol `b06fe2e`; audited application `561b4b1`; Phase 2 source baseline `4f7df97`.
- M2 validated pre-apply code checkpoint: `aa0104f300a41e1de0a75d0af7e3691d0eac8d91`.
- Final applied-state checkpoint is the commit containing this handoff; resolve it below.
  Remote target `origin/feat/warehouse-foundation`; verify actual publication and clean status.
- No main merge or deployment. Git does not roll back committed database changes.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -4 --oneline
git log -1 --format="%H %s" -- WORK_STATE.md
uv sync --locked --group data --group warehouse
uv run --locked --group warehouse python -m src.warehouse inspect
uv run --locked --group warehouse python -m src.warehouse migrate
uv run --locked --group warehouse python -m src.warehouse verify
./scripts/check.ps1 -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

First-bootstrap rehearsal/integration commands require an empty isolated target; see
[development warehouse](docs/warehouse-development.md). Never include credentials here.
