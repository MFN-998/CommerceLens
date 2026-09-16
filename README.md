# CommerceLens

**From commerce data to business decisions.**

CommerceLens is an e-commerce analytics and decision-intelligence portfolio project.
The planned product brings together reliable data pipelines, SQL analytics, customer
intelligence, delivery-risk prediction, forecasting, and business recommendations.

**Current stage: Phase 1 — Project Foundation & Environment.** This repository currently
contains a minimal FastAPI service and Next.js development page, not a completed analytics product.
No dataset has been downloaded. The planned Olist dataset is historical anonymized data;
the future public application will not present it as a live business feed.

## Start here

- [Canonical master plan](docs/master-plan.md): scope, architecture, and phase boundaries.
- [Step-by-step setup](docs/development.md): installation, startup, verification, and troubleshooting.
- [Phase 1 checklist](docs/phase-1-status.md): verified work and remaining prerequisites.
- [Architecture decisions](docs/decisions/0001-foundation.md): what we chose and why.

## Foundation architecture

One Git repository contains two local processes:

```text
Browser -> Next.js (web/, port 3000)
Developer -> FastAPI (api/, port 8000) -> /health and /docs
```

Phase 1 verifies the two processes independently. Product-level frontend/API integration
is scheduled for Phase 6. The master plan's eventual flow remains:

```text
Olist -> raw -> staging -> core -> marts / features -> FastAPI -> Next.js
```

Database configuration and dbt belong to Phase 3. Analytics, model training, public
deployment, and the complete application navigation are not implemented here.

## Quick start (PowerShell)

Prerequisites: Git, uv, Node.js 24.18.0 with npm 11.16.0. Python 3.13.14 is selected by
`.python-version`; uv can install it if unavailable. Run commands from the repository root.

```powershell
Set-Location 'D:\My Projects\CommerceLens'
uv sync --locked
npm --prefix web ci
Copy-Item .env.example .env
uv run --locked uvicorn api.app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location 'D:\My Projects\CommerceLens'
npm --prefix web run dev
```

Open <http://localhost:3000>, <http://127.0.0.1:8000/health>, and
<http://127.0.0.1:8000/docs>. The frontend is a foundation page and shows no business metrics.
Copy `.env.example` only on first setup so you do not overwrite local settings.

## Checks

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

## Working conventions

Use `main` for the stable baseline and short-lived branches such as `feat/data-ingestion`.
Keep commits focused and descriptive, e.g. `feat: initialize CommerceLens foundation`.
Commit dependency manifests and lockfiles together. Keep local `.env` files, datasets,
generated builds, virtual environments, and trained model artifacts out of Git.

Software licensing has not yet been selected by the project owner. Dataset licensing
will be documented during Phase 2 acquisition; it is separate from the code's license.
