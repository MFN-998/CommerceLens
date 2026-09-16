# ADR 0001: Minimal, reproducible project foundation

- Status: Accepted for Phase 1
- Date: 2026-09-16
- Authority: [Master plan](../master-plan.md), sections 22, 27, 31, 36, and 44–45

## Context

CommerceLens combines Python data work, a FastAPI API, and a Next.js frontend. Phase 1
must establish reproducible local development while preserving later phase boundaries.

## Decisions and reasons

1. **One repository, separate `api/` and `web/` directories.** Shared documentation and
   version history make changes across the eventual data/API/UI stack traceable. The
   two applications remain separate processes, consistent with the planned hosting architecture.
2. **Python 3.13.14 with uv.** This installed maintenance-line interpreter provides a
   conservative baseline for the planned scientific Python stack. This does not assert
   that Python 3.14 is incompatible. Future data libraries must be checked when introduced.
   `.python-version` selects the patch release; `requires-python` constrains the minor line.
   The root `.venv` is disposable; `pyproject.toml` and `uv.lock` are the sources for recreating it.
3. **Node.js 24.18.0, npm, Next.js App Router, TypeScript, and Tailwind.** These implement
   the approved frontend stack. npm is already installed and a single frontend does not
   need a JavaScript workspace manager. Commit exact direct versions and `package-lock.json`.
   ESLint and TypeScript catch defects before a browser session. No chart library or
   shadcn/ui component is needed by the minimal page; add them with the first real use.
4. **A small health endpoint, not analytics stubs.** `/health` reports API process
   liveness. It does not check a database or imply data readiness. FastAPI publishes the
   response schema through OpenAPI and `/docs`. Analytics routes arrive in later phases.
5. **Validate backend settings; require no credentials.** Root `.env.example` documents
   the current setting. Pydantic Settings reads `.env` at a stable path and lets process
   environment variables override it. Actual `.env` files are ignored. Future browser-visible
   `NEXT_PUBLIC_*` values must never contain credentials. No cloud project or secret is needed now.
6. **Verify API and web independently.** End-to-end product integration is Phase 6.
   No CORS policy, proxy, database access layer, or mock analytics is necessary for Phase 1.
7. **Create directories when needed.** Future `src/`, `data/`, `dbt/`, notebooks,
   model artifacts, Docker, and CI/CD are introduced in the phases that use them.
   The target tree in the master plan is a destination, not an instruction to fill empty folders.

## Consequences

Developers start two terminals. Locked installs are repeatable; upgrades are intentional
manifest-plus-lockfile changes. The environment remains small and runnable before any
data/cloud work. Future decisions should be recorded as additional numbered ADRs.

This ADR selects implementation details left open by the plan; it does not change scope.

## Tooling compatibility notes

- Use `httpx2` for Starlette's current TestClient, following its documented migration.
- The Next.js 16.3.5 scaffold and its React/accessibility/import lint plugins still select
  ESLint 9; the installed plugin peer ranges do not yet permit ESLint 10. ESLint 9.39.5
  is pinned for compatibility, although upstream support has ended. This is a development
  tooling limitation, not a production runtime dependency. Revisit the complete lint
  toolchain before substantial frontend work; do not force incompatible peer versions.
- uv uses copy mode because the environment is on D: and its cache is on C:; a hard link
  cannot span volumes. This affects installation mechanics, not isolation or dependencies.

## References

- [uv project workflow](https://docs.astral.sh/uv/guides/projects/)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
- [FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/)
- [Starlette test client](https://www.starlette.io/testclient/)
- [ESLint support policy](https://eslint.org/version-support/)
