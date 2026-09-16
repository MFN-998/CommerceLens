# Phase 1: Project Foundation & Environment

Canonical scope: [master plan](master-plan.md), sections 36 and 45.

**Local foundation verified on 2026-09-16. GitHub setup remains pending.**
Do not acquire the Olist dataset until the remaining Phase 1 requirement is satisfied.

## Completed locally

| Requirement | Evidence |
| --- | --- |
| Correct working directory | `D:\My Projects\CommerceLens` |
| Git repository | Initialized with `main`; initial foundation commit contains this report |
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
Only this status report was finalized after those checks; application code and dependencies
were unchanged. The verification is local on Windows; Linux and remote CI were not tested.

## Remaining Phase 1 requirement

The owner must identify the GitHub destination and visibility (an existing repository URL,
or username/organization plus private/public preference). Then connect `origin`, push the
initial commit, and verify the remote branch. No GitHub repository has been created and
no code has been published during this setup.

## Known tooling limitations

- ESLint 9.39.5 is pinned to match the generated Next.js lint plugins' peer ranges, although
  ESLint 9 upstream support has ended. Revisit the lint toolchain before substantial frontend
  development. See [ADR 0001](decisions/0001-foundation.md).
- Starlette 1.6.0 emits one upstream AnyIO deprecation warning in tests; all tests pass.
  The obsolete HTTPX dependency was replaced with its documented `httpx2` replacement.
- npm reports a pending optional `unrs-resolver` install-script approval. No blanket
  approval was granted; lint, type checks, fresh installation, and builds succeeded as installed.
- Code licensing is an owner decision still to be made. No license grant was invented.

## Explicitly deferred

Dataset acquisition and profiling (Phase 2), PostgreSQL/Supabase/dbt (Phase 3), analytics
and KPI definitions (Phases 4–5), frontend/API product integration and public deployment
(Phase 6), ML and decision support (later phases), and production CI/CD (Phase 10).

Start with [the development walkthrough](development.md) to understand and rerun each step.
