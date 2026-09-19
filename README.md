# CommerceLens

**From commerce data to business decisions.**

CommerceLens is an e-commerce analytics and decision-intelligence portfolio project.
The planned product brings together reliable data pipelines, SQL analytics, customer
intelligence, delivery-risk prediction, forecasting, and business recommendations.

**Phases 1–2 complete: foundation, source acquisition, profiling, and local staging.**
The repository contains a minimal FastAPI service, Next.js development page, and a
reproducible Olist data pipeline. The source is historical anonymized data; it is not a
live business feed. Local staging preserves documented source-quality warnings.

## Start here

- [Canonical master plan](docs/master-plan.md): scope, architecture, and phase boundaries.
- [Step-by-step setup](docs/development.md): installation, startup, verification, and troubleshooting.
- [Phase 1 checklist](docs/phase-1-status.md): completion evidence and known tooling limitations.
- [Data setup](data/README.md): acquire, verify, and profile pinned Olist version 2.
- [Phase 2 plan](docs/phase-2-plan.md) and [completion evidence](docs/phase-2-status.md).
- [Quality report](docs/data-quality-report.md) and [column dictionary](docs/data_dictionary/initial.md).
- Architecture decisions: [foundation](docs/decisions/0001-foundation.md) and
  [source quality and local staging](docs/decisions/0002-source-quality.md).

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
uv run --locked --group data pytest
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

## Working conventions

Use `main` for the stable baseline and short-lived branches such as `feat/data-ingestion`.
Keep commits focused and descriptive, e.g. `feat: initialize CommerceLens foundation`.
Commit dependency manifests and lockfiles together. Keep local `.env` files, datasets,
generated builds, virtual environments, and trained model artifacts out of Git.

Software licensing has not yet been selected by the project owner. The source dataset
is listed by Kaggle under CC BY-NC-SA 4.0; attribution and the source/license links are
recorded in [data setup](data/README.md). Dataset and software licensing are separate.
