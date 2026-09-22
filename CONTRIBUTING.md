# Development and review workflow

Read the [master plan](docs/master-plan.md), [engineering standards](docs/engineering-standards.md),
and current phase status before changing CommerceLens. The standards are a permanent owner requirement.

Read [WORK_STATE.md](WORK_STATE.md) and the permanent
[execution protocol](docs/execution-protocol.md) on every new/resumed session. Reconcile
the handoff with actual Git/files before editing. Check exposed usage before major units,
work in independently verifiable milestones, and update the handoff during work. Use
pre-risk checkpoints for broad changes and database-specific recovery plans for migrations.
End substantial sessions COMPLETE or SAFE TO RESUME with an appropriate Git checkpoint,
honest validation/failures, and exact next actions; never rely only on chat history.

## Setup and branches

Use [development setup](docs/development.md) and [data setup](data/README.md). From the
repository root, install reproducibly:

```powershell
uv sync --locked --group data --group warehouse
npm --prefix web ci
```

Check `git status` first; preserve existing work. Branch from the reviewed baseline for
the task, with names such as `feat/warehouse-staging`, `fix/source-validation`, or
`chore/engineering-audit`. `main` is the stable integration branch. A feature branch
being pushed does not mean it was merged, deployed, or checked by CI.

## Quality gates

Stop any Next development server in this checkout before running a production build.
From PowerShell at the repository root:

```powershell
./scripts/check.ps1
```

This fails on Python lint/format/type/test errors, incompatible installed Python packages,
frontend format/lint/type errors, or a failed production build. It includes all offline
API and data tests. It needs the dependencies above, but no dataset, account, or database.
The script preserves the caller's working directory and stops on the first failure.

For dbt tooling/configuration/model changes, include the optional transform group:

```powershell
uv sync --locked --group data --group warehouse --group transform
./scripts/check.ps1 -Transform -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

`-Transform` verifies the pinned dbt version, performs offline project parsing, and includes
its dependencies throughout the gate. It disables dbt anonymous usage reporting and restores the caller's setting.
It does not imply a database connection or model build; those require explicit checks.

For source/data changes, additionally verify the acquired snapshot and regenerate reports:

```powershell
./scripts/check.ps1 -Data
```

This requires the pinned raw data already acquired through `data/README.md`. It may update
report timestamps; review those changes. A failing run preserves earlier staging, so check
the current report status before downstream use. Do not edit raw data to make checks pass.

For dependency changes and before publishing significant changes, run advisory and secret scans:

```powershell
./scripts/check.ps1 -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

`-Security` includes the optional locked Python audit group, queries PyPI/npm advisory
services, and scans Git history using Gitleaks. Package names/versions go to advisory
services; application records and secrets are not required. These online checks fail
when unavailable; an unavailable scan is not a clean result. The local Gitleaks path
above is the audited Windows installation, ignored by Git. On another machine install
[Gitleaks](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) from its official
release, verify its published checksum, and pass its executable path (or put it on PATH).
Version 8.30.1 was used for this audit; review newer releases intentionally.

History scans do not cover changes that have not been committed. Before committing, export
the staged Git tree into an otherwise empty ignored directory and scan that export with
`gitleaks dir <export-directory> --redact --no-banner`. Inspect any finding locally without
publishing secret values. Before pushing, rerun the history scan including the new commit.

For targeted work, individual commands remain available:

```powershell
uv run --locked --group data --group warehouse mypy
uv run --locked --group data --group warehouse pytest
uv run --locked --group data --group warehouse ruff check .
uv run --locked --group data --group warehouse ruff format .
npm --prefix web run format
npm --prefix web run format:check
```

Formatting commands change files; check commands do not automatically repair code.
For API-only tests, `uv run --locked pytest api/tests` remains available. Python tests
use `.pytest-tmp`, a disposable directory that pytest clears. Never store source there.
On macOS/Linux use the individual commands above, or PowerShell 7 for the gate script;
cross-platform execution must be verified before being claimed.

## Reviews, commits, and delivery

Review `git diff` and `git diff --cached --check`. Stage intended paths, inspect staged
files, and ensure secrets/datasets/build outputs are excluded. Keep commits meaningful
and focused; include lockfiles with dependency changes. Use the PR template to explain
the behavior change, validation evidence, phase impact, and remaining risks.

Do not force-push shared history, merge without authorization, or equate a successful
local build with a production release. A solo project can document independent review
without inventing a second human approver. Verify GitHub protection/required-check settings
before collaborative merges; they are external configuration, not guaranteed by this file.

An exception must describe severity, reason, mitigation, owner, and revisit gate in the
current audit/phase record. Failures must not be hidden by disabling checks or adding
blanket suppressions. Keep future security, migration, a11y, and production decisions
visible during development, not postponed to an unspecified cleanup phase.

Warehouse setup and explicit real-database checks are documented in
[development warehouse](docs/warehouse-development.md). Offline checks do not connect to Supabase.

Restricted dbt configuration and real-account verification are documented in
[dbt development setup](docs/dbt-development.md).
