# Phase 1–2 engineering audit

Audit date: **2026-09-20**. Baseline: `4f7df972ef6c71a658a2641564aeb9338a8d1d30`.
Scope: all tracked Phase 1–2 source, configuration, locks, documentation, Git history,
and local source/staging integrity. Phase 3 has not started.

**Status: complete. The local foundation is ready for Phase 3 with the explicit
exceptions and later-stage gates below. It is not yet a production deployment.**
Audit branch: `chore/phase-1-2-engineering-audit`, based on the completed Phase 2 branch.

This audit implements the owner's permanent [engineering standards](engineering-standards.md).
The original master-plan text is preserved with a dated owner addendum linking the standards.
Root `AGENTS.md`, `CONTRIBUTING.md`, the local check script, and the review template carry
the requirement into future work.

Severity: **critical** means stop work/release for immediate material exposure or corruption;
**important** means fix before Phase 3 unless a specific bounded exception is justified;
**recommended** means proportionate improvement or a named later gate; **optional** means
an owner preference or enhancement without a current correctness/security requirement.

## Coverage of the requested areas

| Area | Assessment and action |
| --- | --- |
| 1. Structure and architecture | Single repo with separate API, web, and data modules remains appropriate. No new services or speculative abstractions. Permanent standards and review instructions added. |
| 2. Source organization and maintainability | Acquisition, conversion, contracts, profiling, and reporting remain separate. API import side effects fixed; targeted typing and regression tests added. |
| 3. Git/repository configuration | Focused audit branch from Phase 2; existing history retained; tracked-file/secret checks; stronger credential/backup ignores; review template added. GitHub protection remains externally unverified. |
| 4. Environment/configuration | Python/npm lockfiles and runtime pins retained. API settings load at factory startup and can be injected into isolated tests. No real credentials required. |
| 5. Security/secrets | History and staged-source scans, dependency advisories, safe configuration review, and source-value disclosure fixes. No protected user-facing operations exist yet; later access-control gates documented. |
| 6. Dependencies | Separate runtime/data/dev/audit groups; exact tooling pins; Node types aligned with runtime; no forced upgrades or blanket install-script approval. ESLint support exception is tracked below. |
| 7. Database design/security | Not implemented in Phases 1–2. Phase 3 now has explicit constraints, types, migrations, privileges, exposure/RLS, indexes, and recovery requirements. No database was provisioned by this audit. |
| 8. Errors and validation | Precision, NUL handling, extreme date/statistic errors, writer conflicts, and report publication corrected; previous good staging protected. |
| 9. Tests and QA | Existing tests expanded with real failure regressions. Offline synthetic fixtures, full Olist verification, API smoke checks, and frontend build/layout checks are distinct evidence. |
| 10. Formatting/lint/types | Ruff retained; mypy with pandas stubs and supported Pydantic plugin added; strict TypeScript/Next lint retained; pinned Prettier enforced. |
| 11. Performance/efficiency | Native CSV parser and vectorized profiling retained; existing strict prescan now also detects NUL. Exact integer parsing trades modest CPU for correctness. No distributed processing or premature optimization. |
| 12. Documentation | Setup reflects application factory, new gates, report recovery, and current preview; permanent standards and this audit added. |
| 13. Workflow | One fail-fast local check command, focused branches/commits, explicit diff review, secret scans, and contributor/PR guidance. No claim that remote CI runs. |
| 14. Deployment readiness | Local build/liveness are verified independently of production readiness. Public release gates are explicit; no hosting/auth/monitoring infrastructure added ahead of its phase. |
| 15. Debt/shortcuts | Corrected actionable defects; bounded tooling and local-job limitations listed below with owner and revisit gates. |

## Corrected findings

| ID / severity | Issue and why it matters | Correction and verification |
| --- | --- | --- |
| A01 — Important | API import created an application and read the developer's `.env` before tests could inject settings. Imports/test collection could fail based on local configuration. | Explicit `create_app` factory; Uvicorn uses `--factory`. Tests cover clean import with invalid ambient config, validation at startup, and explicit settings isolation. |
| A02 — Important | Integer strings passed through floating point: `9007199254740993.0` silently became `9007199254740992` with no parse error. This violated faithful staging. | Exact decimal-to-integer parsing, integral/range checks, explicit nullable dtype. Regression tests cover precision, bounds, invalid forms, and missing values. |
| A03 — Important | The fast CSV parser could truncate a field at an embedded NUL, losing data silently. | Existing record prescan rejects NUL with record context before parsing. Regression confirms failure and protected prior staging; raw bytes remain untouched. |
| A04 — Important | Unknown headers/status/state/payment values could be written into tracked failure diagnostics, undermining aggregate-only reporting. | Unknown headers suppressed; categorical reports expose allowed values and aggregate unknown counts. Regression fixtures confirm unexpected source text is absent from reports. |
| A05 — Important | Concurrent validation runs shared report temp paths and could race during staging/report publication. | Fail-fast validation lock, unique flushed temporary files, atomic per-file replacements and cleanup. Tests verify refusal, lock release, protected reports/staging, and publication failure behavior. |
| A06 — Recommended | Out-of-range timestamps, extreme time spans, or percentile overflow could abort reporting instead of producing actionable failure evidence. | Explicit nanosecond bounds, safe diagnostic date differences, annotated unavailable percentile statistics. Extreme-value regression tests retain blocking schema failures and valid JSON output. |
| A07 — Recommended | Python annotations had no automated gate; frontend formatting was manual. Style/type defects could persist undetected. | Mypy checks API/data implementations with the supported Pydantic plugin and pandas stubs; Prettier checks web source/config. No blanket diagnostic suppression. |
| A08 — Recommended | Node 20 type declarations did not match the selected Node 24 runtime. | `@types/node` aligned to 24.13.6; manifest/lock updated and TypeScript/build checks run. |
| A09 — Recommended | Header content could overflow a narrow screen because it could not wrap. Preview text still described Phase 1 and future data preparation. | Wrapping header and accurate empty-state copy; small/desktop viewport checks and semantic/static accessibility review. No new UI features. |
| A10 — Recommended | Quality commands/review expectations were scattered and the expanded permanent requirement was not persisted. | Master-plan addendum, root instructions, standards, contributor workflow, PR template, and fail-fast `scripts/check.ps1`. Gate results recorded below. |
| A11 — Recommended | Ignore rules covered `.env` but not common local private-key/Kaggle credential/backup artifacts. | Added scoped credential/key/backup ignore patterns; examples remain tracked; staged-source and history secret scans complement ignore rules. |

No critical issue was identified in the audited scope. This does not imply complete
security coverage or production certification. Each corrective code change has a
failure scenario or verification directly tied to the issue, rather than test-volume goals.

## Verification evidence

The full local gate passed:

```powershell
./scripts/check.ps1 -Data -Security -GitleaksPath '.artifacts/tools/gitleaks/gitleaks.exe'
```

| Check | Observed result |
| --- | --- |
| Python lint and formatting | Ruff passed |
| Python static analysis | Mypy passed for 14 API/data source files, including typed API tests; Pydantic plugin enabled |
| Automated tests | 63 passed: 8 API, 13 acquisition, 42 validation; 25 additional regressions since the 38-test Phase 2 handoff |
| Installed dependency consistency | All 70 installed packages in the data/dev/audit environment compatible |
| Known dependency advisories | pip-audit 2.10.1: no known vulnerabilities across 70 packages; npm audit: zero reported vulnerabilities |
| Frontend gates | Prettier, ESLint, strict TypeScript, and Next.js production build passed |
| Full Olist rerun | Nine raw files verified; 1,550,922 rows; zero blocking checks; 29 warning checks; staging action `verified_existing` |
| Artifact integrity | All nine existing Parquet hashes unchanged; source-manifest hash matches staging metadata; JSON, Markdown, and dictionary agree |
| API startup | Factory startup succeeded; `/health`, `/docs`, and `/openapi.json` returned expected responses; missing route returned 404 |
| Responsive preview | Built app checked in installed Chrome at 320px and 1280px; no horizontal overflow or browser exceptions; screenshots visually reviewed |
| Basic accessibility structure | English document language, meaningful title, one main landmark and one h1 verified; semantic structure and narrow layout reviewed |
| Fresh source reproduction | Git tree `4314ef7f4c6b2df1ab654cc0f400f1900641da92` exported without `.env`, environments, datasets, or builds; fresh locked Python install, `npm ci`, and complete offline quality gate passed |
| Secret/repository hygiene | Gitleaks 8.30.1 scanned all reachable history and a staged-source export with no findings; secrets/datasets/builds excluded; diff whitespace checks passed |

Only documentation was finalized after the clean-source export. The data recovery guide
was also staged afterward; implementation, test, dependency, and quality-gate content
match the verified export. Verification ran locally on Windows. No remote CI, full browser
matrix, formal WCAG conformance audit, penetration test, or production deployment is claimed.

Generated browser captures and audit-tool outputs remain in ignored `.artifacts/` for
local diagnostics. They are not application code or repository deliverables. One existing
Starlette/AnyIO deprecation and the reviewed ESLint/npm tooling exceptions below remain visible.

## Explicit exceptions and future gates

The owner for all items below is the **CommerceLens project maintainer**. These are
visible constraints, not completed production controls or hidden acceptance of failed checks.

| ID / severity | Current limitation and mitigation | Revisit / completion gate |
| --- | --- | --- |
| E01 — Important, bounded tooling exception | ESLint 9.39.5 is EOL. Current React/accessibility/import plugins exclude ESLint 10 in peer ranges. Retain compatible dev-only linting; advisory scan is clean; do not force incompatible peers. | Recheck the complete toolchain before substantive Phase 6 frontend work and before a public release; move to supported compatible tooling then. |
| E02 — Recommended | Starlette emits one upstream AnyIO deprecation warning; tests pass. No global warning suppression or unrelated runtime upgrade. | Recheck on FastAPI/Starlette/AnyIO upgrade and before deployment. |
| E03 — Recommended | npm reports an optional unrs-resolver install script without approval. Installed lint/type/build work; no blanket script execution granted. | Review the specific script only if a supported install/platform needs it; verify clean install then. |
| E04 — Recommended | Data processing is local/in-memory; reports publish individually, and hard termination can leave a lock. Raw/staging are protected; JSON is authoritative and recovery is documented in `data/README.md`. | Revisit for unattended scheduling/concurrent users or materially larger data. Test retry/transaction behavior before treating it as a service. |
| E05 — Important downstream data gate | 29 source-quality warnings remain intentionally preserved. Nonunique geography/reviews, lifecycle anomalies, missing attributes, and child-table joins need explicit eligibility/grain decisions. Float staging is not an accounting policy. | Phase 3: exact monetary database types, tested constraints/relationships, unique dimension mappings, and separate child aggregation before combining measures. |
| E06 — Recommended, stage-dependent | Database credentials, access controls, migrations, backup/restore, and network/RLS policies do not exist because there is no database yet. | Phase 3 before exposing/loading shared or irreplaceable state: document and test the applicable controls and restore approach. |
| E07 — Recommended, stage-dependent | Auth/authorization, public API limits, HTTPS/headers, production diagnostics, rollback, retention, browser matrix, and interactive a11y/E2E checks are not implemented for this static local preview. | Add controls with the corresponding feature; verify them before any public deployment or protected-data exposure. |
| E08 — Recommended, stage-dependent | Local gates are implemented; remote CI/CD and GitHub required checks/branch protections were not configured or verified. | Verify branch rules before collaborative merges; introduce CI/CD at its planned stage or explicitly document a justified earlier adjustment. |
| E09 — Optional owner decision | The code has no selected license. Olist attribution/license remains separately documented. No software license grant was invented. | Owner selects intended reuse terms before distributing code under an asserted license. |
| E10 — Recommended | Static data typing is gradual and KaggleHub has no typing metadata. Runtime dataframe contracts and regression tests cover the dynamic boundary; only that third-party import is exempted. | Tighten shared public report contracts if their consumers expand; recheck upstream typing on upgrade. |

Current warnings and later-stage controls do not block a local Phase 3 start once the
audit checks pass. They do block claiming that the application is already production ready.

## Standards and scan sources

- [OWASP ASVS](https://github.com/OWASP/ASVS) and [OWASP API Security](https://owasp.org/www-project-api-security/).
- [ESLint support policy](https://eslint.org/version-support/): v9 EOL since 2026-08-06;
  current plugin compatibility checked against npm package metadata on the audit date.
- [PyPA pip-audit](https://github.com/pypa/pip-audit) for known Python package advisories;
  npm audit for frontend advisories. An advisory database does not detect every supply-chain risk.
- [Gitleaks 8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), official Windows
  release verified against its published SHA-256 checksums. Scans redact finding values.

## Phase 3 follow-up — 2026-09-22

E05/E06 are partially addressed: versioned/checksummed migrations, verified TLS, private
role boundaries, protected credentials and actual-login tests, atomic complete loading,
full text/count/decimal reconciliation, idempotent retry and rollback fixtures now exist.
All 1,550,922 source rows are verified; see [M3 acceptance](warehouse-load-verification.json).
Dbt/model/join tests, populated reconstruction, deployment network controls and
protected backup/restore for shared or irreplaceable state remain explicit gates.
Historical Phase 1–2 observations above retain their original audit-date meaning.
