# Phase 1: Project Foundation & Environment

Canonical scope: [master plan](master-plan.md), sections 36 and 45.

**Phase 1 complete. Local foundation and GitHub connection verified on 2026-09-16.**
This is the historical foundation record. Phase 2 subsequently began on 2026-09-19;
see its separate [plan](phase-2-plan.md) and [completion record](phase-2-status.md).
The [2026-09-20 engineering audit](engineering-audit-phase-1-2.md) records subsequent
hardening and current verification. Use the updated development guide's factory startup command.

## Completed

| Requirement | Evidence |
| --- | --- |
| Correct working directory | `D:\My Projects\CommerceLens` |
| Git repository | Initialized with `main`; initial foundation commit contains this report |
| GitHub connection | [MFN-998/CommerceLens](https://github.com/MFN-998/CommerceLens); `main` tracks `origin/main`; foundation pushed and remote commit verified |
| Master plan preserved | `docs/master-plan.md` copied from the supplied plan; working copy matched the supplied text exactly |
| Python environment | Python 3.13.14, uv 0.11.14, isolated root `.venv`, exact direct versions, committed `uv.lock` |
| Frontend environment | Node.js 24.18.0, npm 11.16.0, Next.js 16.3.5, React 19.2.8, TypeScript 5.9.3, Tailwind 4.3.3 |
| Configuration | Safe `.env.example`; root `.env` ignored; backend runs without cloud credentials |
| Documentation | README, development walkthrough, canonical plan, ADR 0001 |
| Backend checks | Ruff lint and formatting passed; 5 API/configuration tests passed |
| Frontend checks | ESLint, TypeScript, and production build passed |
| API startup | Uvicorn development server started; `/health`, `/docs`, and `/openapi.json` returned HTTP 200 |
| Health contract | `{"status":"ok","service":"commercelens-api"}` |
| Frontend startup | Next.js development server started; HTTP 200 and browser visual check passed |
| Reproducibility | Fresh staged-source export, without `.env`, `.venv`, `node_modules`, or `.next`, passed locked Python install, all 5 API tests, `npm ci`, and production build |
| Ignore rules | Local secrets, environments, builds, test scratch files, future raw data and model binaries excluded; examples and lockfiles included |

The clean export used Git tree `45669aed69d918979fb2f546a946f6e798cd680c`.
Documentation was finalized after those checks; application code and dependencies
remain unchanged. The verification is local on Windows; Linux and remote CI were not tested.

## GitHub verification

- The owner selected the existing repository `https://github.com/MFN-998/CommerceLens`.
- `origin` is configured as `https://github.com/MFN-998/CommerceLens.git`.
- Its original commit `5a54297` contained a title-only README. Both that commit and the
  local foundation commit `949651c` are preserved in merge commit `05ad05d`.
- The detailed local README retains the same project title and supplies the setup instructions.
- The initial push succeeded, and a direct remote query confirmed GitHub stored commit
  `05ad05dff5f9b905abc5584d8848c8939c6d7ef5` on `main` before this documentation update.
- Local `main` tracks `origin/main`. No force push, repository recreation, or visibility
  change was used. No public application deployment or remote CI run is claimed.

All Phase 1 exit requirements are satisfied. This report records completion and does not
authorize starting a later phase.

## Known tooling limitations

- ESLint 9.39.5 is pinned to match the generated Next.js lint plugins' peer ranges, although
  ESLint 9 upstream support has ended. Revisit the lint toolchain before substantial frontend
  development. See [ADR 0001](decisions/0001-foundation.md).
- Starlette 1.6.0 emits one upstream AnyIO deprecation warning in tests; all tests pass.
  The obsolete HTTPX dependency was replaced with its documented `httpx2` replacement.
- npm reports a pending optional `unrs-resolver` install-script approval. No blanket
  approval was granted; lint, type checks, fresh installation, and builds succeeded as installed.
- Code licensing is an owner decision still to be made. No license grant was invented.

## Deferred at the Phase 1 handoff

Dataset acquisition and profiling (Phase 2), PostgreSQL/Supabase/dbt (Phase 3), analytics
and KPI definitions (Phases 4–5), frontend/API product integration and public deployment
(Phase 6), ML and decision support (later phases), and production CI/CD (Phase 10).

Start with [the development walkthrough](development.md) to understand and rerun each step.
