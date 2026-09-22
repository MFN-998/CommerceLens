# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M3 COMPLETE; M4 IN PROGRESS.
- Current milestone: pinned dbt tooling adopted and validated in the actual project.
- Current task: implement restricted transformer access and minimal dbt configuration.
- Objective: tested analytical warehouse; staging/core models and M5 marts still pending.
- Tooling unit COMPLETE / SAFE TO RESUME. M3 source snapshot remains populated and unchanged.

## Completed Work

- M3: all nine source tables and 1,550,922 rows committed, exact text/count/money and
  unchanged-source verification passed; complete rerun verified_existing with same identity.
  See docs/warehouse-load-verification.json and source-loading recovery guide.
- Resumed clean 2604e82. Live load registry identity and migration checksums match Git.
- Added optional transform dependency group: dbt-core 1.12.5 and dbt-postgres 1.11.0.
  Adopted reviewed single lock; installed with existing data/warehouse/dev/audit groups.
- Added scripts/check.ps1 -Transform to include dbt tooling/version checks, with telemetry
  disabled for that invocation and the caller's environment restored afterward.
- Full actual-project quality/advisory gate passed. No database mutations in this unit.

## Files

- Modified: pyproject.toml, uv.lock, scripts/check.ps1, CONTRIBUTING.md,
  docs/dbt-setup-plan.md, docs/phase-3-plan.md, WORK_STATE.md.
- No repository files deleted/renamed; source data, migrations and loaded rows unchanged.
- Protected .env.warehouse and .env.warehouse.loader exist and stay ignored.
- Transformer/dbt bootstrap candidates are being reviewed outside Git in the local
  ChatGPT workspace's m4-staging. They are not implemented repository features yet.

## Technical Decisions

- dbt remains optional tooling, separate from FastAPI runtime dependencies. One manifest/lock.
- Shared transitive changes: pathspec 1.1.1 → 1.0.4; protobuf 7.36.2 → 6.33.6.
  Existing direct pins retained. Core 1.12 supports the mypy/pathspec intersection.
- Transformer will get a separate NOINHERIT LOGIN member only of commercelens_transformer;
  private configuration, verified TLS, explicit role and no administrator fallback.
- Planned dbt profiles contain environment references only; parse must work offline without
  real credentials. Initial schemas staging/core/marts only, one thread and view materialization.
- Free/views storage policy remains: raw ceiling 367M bytes, database ceiling 400M bytes.
  Fresh capacity/performance review before materializing. No paid upgrade or source omission.

## Validation

- Actual environment: dbt Core 1.12.5 / Postgres 1.11.0; 111 installed packages compatible.
- Full -Transform -Security gate passed: 151 offline tests, 13 explicit live cases skipped;
  Ruff lint/format, mypy (21 source files), frontend format/lint/types/build,
  Python/npm advisory scans and Git-history secret scan. Existing AnyIO warning remains.
- M3 historical evidence: all 10 actual-loader recovery cases and restricted-login access
  passed separately; full source COPY and complete idempotent verification passed.
  Last accepted raw/database sizes: 275,750,912 / 287,026,323 bytes. API schemas private.
- This resume rechecked live migration hashes and load registry; no redundant full data reload.
- Transformer login, dbt parse/debug/build/models: Not yet implemented or tested in repository.

## Current Repository Condition

CLEAN / STABLE at the containing tooling checkpoint. M3 remains verified and populated.
SAFE TO RESUME with transformer access/configuration. Do not rerun empty-target fixture
tests against the populated database or provision the existing loader again.

## Incomplete Work

- Review/integrate transformer purpose/provisioning and rollback-only actual-login tests.
- Review/integrate minimal dbt project, nine sources, restricted schema macro, safe profile
  and parse/debug wrapper. Run offline parse, actual debug and ownership/denial tests.
- Then implement staging/core models and tests; M5 technical marts/queries/reconstruction.
- Audit E01–E10 retain revisit gates; E05/E06 have documented partial Phase 3 remediation.
- No known failing check. No reset credit, paid upgrade, merge, deployment or production claim.

## Exact Next Actions

1. Inspect current status/history and usage. Read docs/dbt-setup-plan.md and ADR 0003/0004.
2. Review the m4-staging candidates against actual repository config/credentials;
   preserve loader compatibility, private file safeguards and rollback-only tests.
3. Integrate configuration/CLI and dbt bootstrap; run full gate plus offline parse.
   Checkpoint before actual transformer provisioning. Verify role/file absence first.
4. Provision once; verify actual role boundaries/TLS/view ownership and dbt debug, then
   checkpoint configuration before staging/core model implementation.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Published M3 acceptance 2604e82; atomic loader 35ba3c5; loader tooling e428801.
- Tooling adoption is the containing commit; verify final status and publication.
- Resolve handoff with git log -1 --format="%H %s" -- WORK_STATE.md.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
uv sync --locked --group data --group warehouse --group transform
./scripts/check.ps1 -Transform -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
uv run --locked --group warehouse python -m src.warehouse inspect
```

Use the source load command for full verification only when needed; it re-reads all data.
Never print credentials, raw rows or sensitive database errors. All databases here remain development.
