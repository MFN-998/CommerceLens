# Development walkthrough

The local checkout is `D:\My Projects\CommerceLens`. All commands below use PowerShell.
Commands for another machine should use that machine's actual checkout path.

This guide covers the application foundation. Continue with [data setup](../data/README.md)
for the Phase 2 acquisition, validation, and staging walkthrough.

## 1. Understand the repository

`api/` holds FastAPI code and tests. `web/` holds Next.js. `docs/` holds the canonical
master plan, development instructions, status, and architecture decisions. Keeping these
in one repository makes the application's changes reviewable together, while keeping
Python and JavaScript responsibilities distinct.

Git tracks source files and dependency lockfiles. It should not track things that can
be regenerated, local credentials, or large datasets. `.gitignore` implements this rule.
`.editorconfig` and `.gitattributes` keep text formatting consistent across Windows and Linux.

## 2. Verify prerequisites

```powershell
Set-Location 'D:\My Projects\CommerceLens'
git --version
uv --version
node --version
npm --version
```

Validated runtime targets: Python 3.13.14, Node.js 24.18.0, npm 11.16.0. uv manages the
Python environment; the setup was prepared with uv 0.11.14. Node is selected separately:
`.node-version` documents the version but does not switch the installed executable itself.

Official installation references: [Git](https://git-scm.com/downloads),
[uv](https://docs.astral.sh/uv/getting-started/installation/),
[Node.js](https://nodejs.org/en/download).

## 3. Recreate the Python environment

```powershell
uv sync --locked
uv run --locked python --version
```

`uv sync` creates a project-local `.venv` and installs the packages selected in `uv.lock`,
including development tools. `--locked` makes it fail if the manifest and lockfile disagree,
instead of silently choosing new versions. uv can obtain the pinned Python version if needed.
Use `uv run --locked` so there is no need to activate a virtual environment manually.

Current runtime dependencies serve the API: FastAPI, Pydantic Settings, and Uvicorn.
Development dependencies provide tests, the HTTP test client, and Ruff. Phase 2 adds
pandas, Pandera, PyArrow, and KaggleHub in the optional `data` dependency group. Use
`uv sync --locked --group data` for data work. Include `--group data` in data commands
because uv synchronizes the selected groups on each run.

For intentional changes use `uv add package-name` or `uv add --dev package-name` and
review both `pyproject.toml` and `uv.lock`. Avoid installing arbitrary packages into the
global Python or creating a second requirements file with conflicting versions.

## 4. Configure local settings

On first setup only:

```powershell
Copy-Item .env.example .env
```

The current setting is `COMMERCE_ENVIRONMENT=development`. The backend can run using its
safe default even without `.env`. The file is read from the repository root. An actual
process environment variable overrides the same setting from `.env`.

The current frontend needs no environment variables. When frontend configuration becomes
necessary, Next.js reads its files inside `web/`, for example `web/.env.local`. Variables
prefixed with `NEXT_PUBLIC_` can be included in browser code and must never contain secrets.
Add a safe example file when adding new settings. Never paste real credentials into Git.

## 5. Start and understand the backend

```powershell
uv run --locked uvicorn api.app.main:app --reload --host 127.0.0.1 --port 8000
```

Uvicorn is the process serving the FastAPI application. `api.app.main:app` names the Python
module and application object. `--reload` restarts it when development code changes.
Binding to `127.0.0.1` keeps this development server on your own machine.

Open <http://127.0.0.1:8000/health>. Expected JSON:

```json
{"status":"ok","service":"commercelens-api"}
```

Open <http://127.0.0.1:8000/docs> to inspect and try the endpoint. `/openapi.json` is its
machine-readable schema. A healthy process does not mean a warehouse or trained model
exists. The endpoint deliberately makes no such claim.

## 6. Recreate and start the frontend

In a second terminal at the repository root:

```powershell
npm --prefix web ci
npm --prefix web run dev
```

`npm ci` installs exactly the frontend lockfile and fails on manifest/lockfile mismatch.
It replaces `web/node_modules` if present; dependencies are disposable, source files are not.
The `--prefix web` argument tells npm which application to operate on.

Open <http://localhost:3000>. You should see CommerceLens and its Phase 1 status, with
an honest empty state for future analytics. `web/app/page.tsx` is the page, `layout.tsx`
provides shared page structure, and `globals.css` loads Tailwind and shared styles.

TypeScript checks code contracts. Tailwind supplies styling utilities. App Router maps
the `app/` directory to routes. No mock KPIs, dashboard navigation, or charting packages
are necessary at this stage. The API and frontend run independently in Phase 1.

Press Ctrl+C in each terminal when finished. Do not run Next.js development and production
build commands concurrently in the same checkout, since they share generated output.

## 7. Verify changes

Stop the frontend development server before building:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked --group data pytest
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

API tests check the health contract, OpenAPI documentation, missing-route behavior, and
configuration precedence/validation. Frontend linting and type checking find source defects;
the production build checks that the application can be compiled for deployment later.
Data tests exercise acquisition integrity, schema failures, relationships, and complete
Parquet round trips with synthetic fixtures. They do not download Olist or require a
database. For API-only work, `uv run --locked pytest api/tests` needs no data group.

Pytest scratch files live in `.pytest-tmp`, which pytest clears on each run.
Do not put source files or personal files there. This avoids a Windows permissions conflict
with the machine's pre-existing shared pytest temporary folder.

To run the compiled frontend locally after a successful build:

```powershell
npm --prefix web run start
```

For reproducibility, a fresh clone should succeed using the same locked install and check
commands. `.venv` and `node_modules` must be recreated, never copied between checkouts.

## 8. Git and GitHub

`main` is the stable baseline. Use short-lived branches named after the change:

```powershell
git switch -c feat/data-ingestion
git status --short
git diff
```

The example branch belongs to Phase 2; create it only after Phase 1 passes. Review files
before staging. Commit messages should describe the change, such as
`feat: initialize CommerceLens foundation`. Commit lockfiles with their manifests.

Git stores local history. GitHub stores a remote copy and supports collaboration.
The repository is [MFN-998/CommerceLens](https://github.com/MFN-998/CommerceLens).
`origin` points to `https://github.com/MFN-998/CommerceLens.git`, and local `main` tracks
`origin/main`. The original GitHub README commit and local foundation history were merged
and published together. The existing repository visibility was left unchanged.

To inspect the connection and refresh your view of the remote branch:

```powershell
git remote -v
git fetch origin
git status --short --branch
```

Committing records changes locally. `git push` publishes commits on the current branch
to its configured upstream; on `main`, that is `origin/main`. New feature branches need
their own upstream, for example `git push --set-upstream origin feat/data-ingestion`.
Pushing to GitHub does not deploy the application. Phase 2 work uses `feat/data-ingestion`;
see its [completion record](phase-2-status.md) for the data handoff.

## Troubleshooting

- **Wrong directory:** use the root `Set-Location` command before Python commands.
- **PowerShell blocks npm.ps1:** use `npm.cmd` instead of changing machine execution policy.
- **Port already in use:** stop your old server with Ctrl+C or select another port explicitly.
  Do not stop an unrelated process just to claim its port.
- **Python mismatch:** inspect `uv run --locked python --version`, not the global `python`.
- **Lock mismatch:** review the dependency change, regenerate the relevant lock intentionally,
  and commit both files; do not delete lockfiles as a routine fix.
- **Network or authentication error:** resolve that access issue; do not disable TLS verification.
- **Unknown environment value:** use development, test, or production; invalid values fail startup.

## Phase boundary

Phase 1 established the application foundation. Phase 2 adds source acquisition,
profiling, validation, and local staging. PostgreSQL/Supabase and dbt begin in Phase 3;
business analytics, product integration, ML, deployment, and CI/CD remain in their
master-plan phases. See [Phase 1 status](phase-1-status.md) and [Phase 2 status](phase-2-status.md).
