# CommerceLens work state

Updated: 2026-09-22. Repository: `D:\My Projects\CommerceLens`.
Read with AGENTS, master plan, engineering standards and execution protocol.

## Project State

- Phases 1–2/audit COMPLETE; Phase 3 M1–M3 COMPLETE; M4 IN PROGRESS.
- Current milestone: dbt tooling and offline bootstrap COMPLETE; live setup pending.
- Current task: establish a pre-provision checkpoint, then verify the transformer account.
- Objective: tested analytical warehouse; staging/core models and M5 still pending.
- SAFE TO RESUME. Usage constrained (last observed 6% five-hour / 11% weekly remaining);
  preservation mode: live provisioning deferred so validation/recovery has adequate capacity.

## Completed Work

- M3: nine source tables / 1,550,922 rows, exact text/count/money and idempotent replay
  verified; docs/warehouse-load-verification.json holds immutable acceptance evidence.
- Resumed clean 2604e82, rechecked live migration checksums and load registry identity.
- dfecdbc adopted pinned optional dbt tooling and passed the full project quality gate.
- Added restricted transformer purpose/shared provisioning, preserving tested loader
  safeguards; minimal dbt project/profile, nine raw sources, approved-schema macro.
- Added isolated parse/debug wrapper, offline/secret-handling regression coverage,
  rollback-only actual-login integration test and offline parse in the quality gate.
- Fixed the CLI Literal type inference failure; full gate now passes.

## Files

- Created: dbt/dbt_project.yml, dbt/profiles/profiles.yml, dbt/models/sources.yml,
  dbt/macros/generate_schema_name.sql, src/warehouse/dbt_runner.py,
  tests/test_warehouse_dbt.py, tests/test_warehouse_transformer_access_integration.py,
  docs/dbt-development.md.
- Modified: src/warehouse/{config,credentials,__main__}.py, corresponding config,
  credentials and CLI tests, scripts/check.ps1, CONTRIBUTING.md, docs/dbt-setup-plan.md,
  docs/phase-3-plan.md and this file. Tooling checkpoint changed pyproject.toml/uv.lock.
- Nothing deleted/renamed. Applied migrations and source data unchanged.
- Protected .env.warehouse/.env.warehouse.loader remain ignored; transformer file absent.

## Technical Decisions

- Optional transform group: dbt-core 1.12.5 / dbt-postgres 1.11.0, single manifest/lock.
  Shared transitive changes pathspec 1.1.1 → 1.0.4 and protobuf 7.36.2 → 6.33.6.
- Separate NOINHERIT transformer LOGIN; explicit capability role, verify-full/trusted CA,
  private credential file, no admin fallback, no overwrite and uncertain-commit recovery.
- Offline parse uses synthetic complete settings with no private-file reads or connection.
  Debug uses only transformer settings. Fixed safe diagnostics; telemetry/file logs off.
- One thread, views, only staging/core/marts schema names. No raw writes or API exposure.
- Free/views policy: raw ceiling 367M bytes, database ceiling 400M; review capacity and
  performance before materialization. No paid upgrade, source omission or business KPIs.

## Validation

- Full -Transform -Security gate passed on 2026-09-22: 203 tests / 14 opt-in live cases
  skipped; Ruff lint/format; mypy 22 source files; offline dbt parse; frontend formatting,
  lint/types/build; 111 installed packages compatible; Python/npm advisory scans clean;
  Git history secret scan clean. Existing documented AnyIO deprecation warning remains.
- Offline tests exercised actual dbt parsing and a deliberately failed debug with network
  guards; they verify schema selection and synthetic secret absence, not live credentials.
- Transformer file absent; ignore rules cover credentials and generated dbt artifacts.
- Live transformer access/TLS/ownership and dbt debug: Not yet tested. No model build.
- Historical M3: all 10 live loading/recovery cases, actual loader access, full COPY and
  verified-existing replay passed. Raw/database bytes 275,750,912 / 287,026,323.
- This resume rechecked migration checksums and load registry without reloading sources.
- No E2E/deployment validation applies to this setup unit; no production readiness claim.

## Current Repository Condition

CLEAN / STABLE implementation; documentation and bootstrap pending the containing
checkpoint at writing. Full gate passed. SAFE TO RESUME; M3 remains populated.
Do not rerun empty-target fixtures on this database or reprovision the existing loader.

## Incomplete Work

- Provision transformer once; verify real identity/TLS, denied privileges, view ownership,
  cleanup and dbt adapter debug. Credentials/role have not been created by this unit.
- No staging/core models, dbt data tests/build or M5 marts/SQL/reconstruction yet.
- Audit E01–E10 revisit gates remain; E05/E06 have documented partial Phase 3 remediation.
- No known failing checks. No reset credit, paid upgrade, merge or deployment.

## Exact Next Actions

1. Read docs/dbt-development.md; inspect status/history and usage. Check whether
   .env.warehouse.transformer exists (metadata only); provisioning also checks role absence.
2. With adequate usage for validation/recovery, run provision-transformer once. If file or
   role exists, reconcile before any retry; never delete/overwrite credentials blindly.
3. Run the rollback-only transformer access integration test and dbt-debug from the guide.
   Update this handoff immediately with actual outcome; checkpoint before model work.
4. Implement staging types/quality flags and core dimensions/facts from ADR 0003 in
   atomic tested units. Preserve views-first ADR 0004, source counts and child grains.

## Git State

- Branch feat/warehouse-foundation; main unchanged/unmerged.
- Latest tooling commit dfecdbc; published M3 acceptance 2604e82, loader 35ba3c5.
- Bootstrap/docs are the containing checkpoint; verify final status and publication.
- Resolve handoff commit with git log -1 --format="%H %s" -- WORK_STATE.md.
- Bootstrap staged export and post-commit history scans passed before its verified push.
  Repeat these scans for the final handoff; confirm clean status after publication.

## Continuation Commands

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git status --short --branch
git log -5 --oneline
uv sync --locked --group data --group warehouse --group transform
./scripts/check.ps1 -Transform -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-parse
uv run --locked --group warehouse python -m src.warehouse provision-transformer
uv run --locked --group warehouse --group transform python -m src.warehouse dbt-debug
```

Only provision after the absence/recovery checks above. Actual-login test commands are in
docs/dbt-development.md. Never print credentials, raw records or sensitive driver errors.
