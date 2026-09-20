# CommerceLens engineering standards

Permanent project requirement, adopted by the project owner on **2026-09-20**.
Applies to every phase, significant feature, architectural decision, review, deployment,
and documentation change unless the owner explicitly changes it. This supplements the
[master plan](master-plan.md); it does not redesign the product or its phase sequence.

## Practical standard of work

Build as a small professional team would: make behavior correct, code understandable,
changes reviewable, environments reproducible, and risks visible. Choose the simplest
solution that meets the current need. Do not add a service, framework, abstraction,
dependency, or infrastructure layer merely to resemble a larger company.

Explain consequential choices and their tradeoffs as part of the learning workflow.
Record durable architectural decisions in `docs/decisions/`. A local development
shortcut must name its limitation, mitigation, and the point at which it must be resolved.

## Definition of done for significant changes

1. Confirm the master-plan phase and the problem being solved. Define expected behavior,
   input/output contracts, failure behavior, data grain, and acceptance evidence as applicable.
2. Review security/privacy boundaries, configuration, dependencies, performance implications,
   accessibility, and operational consequences before implementation. Mark irrelevant areas
   as not applicable with a reason rather than adding unused mechanisms.
3. Keep responsibilities separate and interfaces small. Validate data at boundaries, protect
   invariants, use clear names, and avoid duplicated logic, unexplained constants, dead code,
   debugging artifacts, and speculative abstractions.
4. Add tests for meaningful behavior and failure scenarios. Run formatting, lint, applicable
   type checks, tests, and build checks. Dependency/data/UI changes need their additional checks.
5. Review the complete diff, including configuration and lockfiles. Verify no secrets,
   source datasets, local environments, logs, or generated builds enter Git.
6. Update setup/API/schema/architecture documentation as relevant. Explain what changed,
   why, evidence, remaining limits, and any migration/rollback implications in the review.
7. Commit focused changes on a branch. Merge and deployment are separate authorized actions.
   Do not describe a feature as production ready while a release gate remains unresolved.

## Code, architecture, and configuration

- Keep `api/`, `web/`, and data `src/` responsibilities separate in the single repository.
  Introduce shared modules only after a real shared need. Preserve the raw/staging/core/mart
  boundaries when later phases create them.
- Use Ruff for Python style, mypy for API/data implementation checks, strict TypeScript,
  Next ESLint rules, and Prettier for frontend formatting. Use readable public annotations.
  Dynamic dataframe contracts also require runtime validation; static types do not replace it.
- Mypy checks API signatures and all implementation bodies in `api/` and `src/`; data report
  dictionaries remain gradual typing. The only missing-import exception is untyped KaggleHub.
  Do not suppress a finding globally to obtain a green check.
- Separate initialization from imports and permit explicit dependency/configuration injection
  in tests. Environment-specific values belong in validated settings, not source literals.
- Use safe `.env.example` files, ignore local `.env` and credentials, and document precedence.
  Development, test, staging, and production credentials/resources must remain separate.
  Development defaults must not silently enable unsafe production behavior.

## Security and privacy

Use applicable [OWASP ASVS 5.0](https://github.com/OWASP/ASVS) requirements
as verifiable design/review prompts, and [OWASP API Security](https://owasp.org/www-project-api-security/)
for API-specific risks. This is a working baseline, not a claim of ASVS certification or
complete OWASP coverage. Recheck relevant standards when the application surface expands.

- Never commit, print, embed in browser bundles, or put secrets in reports. `NEXT_PUBLIC_*`
  values are public. Use platform secret stores for hosted deployments and least-privilege
  credentials. Rotate/revoke a leaked credential first; deletion from the current tree alone
  does not remove it from history or invalidate it.
- Validate types, lengths, allowed fields, ranges, identifiers, and authorization at trust
  boundaries. Reject unsupported formats safely. Use parameterized queries and context-aware
  output encoding. Do not log or reflect raw sensitive input in public errors or diagnostics.
- Add authentication when identity/protected data is introduced; enforce authorization
  server-side for every protected operation/object. Hiding UI controls is not access control.
  Choose a maintained identity/session solution, avoid homemade crypto, and apply CSRF/session,
  CORS, rate limits, request-size limits, and security headers according to actual exposure.
- Review data collection, retention, access, exports, and logs for minimization. Historical
  anonymized Olist records are not a live feed; aggregate reports must not expose row identifiers
  or review text unnecessarily. Respect dataset attribution/license separately from code licensing.
- Scan repository history for secrets and dependencies for known advisories. A clean scan
  is evidence about those tools/rules at that time, not proof that software is vulnerability-free.

## Dependencies and repository hygiene

- Maintain one Python manifest/lock and one frontend manifest/lock. Use exact direct versions
  where selected, compatible runtime pins, locked installs, and intentional upgrades together.
- Keep runtime, data, development, and audit tools separated. Prefer existing capabilities
  over additional packages; review maintenance, compatibility, advisories, and install scripts.
  Do not use forced dependency upgrades or blanket script approval as a shortcut.
- Exclude secrets, raw/staged data, cache/build outputs, local tools, backups, and model binaries.
  Commit small provenance and aggregate quality evidence intentionally. Scan newly staged work
  as well as history before publication; history-only scans do not cover uncommitted changes.
- Use meaningful commits and focused branches. Avoid force pushes/shared-history rewrites,
  unrelated refactors, and vague commit messages. The PR template records relevant review evidence.

## Data and database engineering

- Preserve raw provenance, source version, checksums, row identity, and documented grains.
  Report parsing failures, missingness, anomalies, and relationship gaps; never silently repair
  source records or change business definitions to make tests pass.
- In Phase 3, use versioned migrations/bootstrap SQL, explicit schemas/types/constraints,
  dbt tests, and reconciliation of rows and monetary measures at the intended grain.
  Use exact decimal warehouse types for money. Aggregate independent child tables before joins.
- Separate owner/migration, loader, transformation, and application privileges as needed.
  Keep credentials server-side; restrict network access and exposed schemas. If Supabase exposes
  tables through its API, explicitly assess grants/RLS and deny unintended anonymous access.
- Add indexes based on keys, joins, filters, and measured query plans. Avoid accidental cross joins,
  N+1 access, repeated full scans, and unbounded API results. Profile before optimizing broadly.
- Before storing irreplaceable/shared database state, define backup retention, restore procedure,
  access protection, and a restore test. Source redownload and ignored local Parquet are not a
  backup strategy for a future database. Test destructive migrations and recovery on isolated data.

## Tests, failures, and performance

- Use small deterministic synthetic fixtures for offline unit/API/data tests; avoid ambient `.env`,
  network dependencies, real secrets, or order-dependent tests. Regression-test confirmed defects.
- Add database/dbt integration tests in Phase 3, metric tests with Phases 4–5, and browser/API/database
  end-to-end tests when real product flows arrive. Add model/feature tests with ML phases.
- Use explicit failure states and nonzero CLI exits. Preserve a previous valid snapshot on failure,
  prevent conflicting writers, and document safe restart/recovery. Do not hide failed checks.
- Log meaningful operational context and correlation IDs when services/jobs need them, using levels
  and redaction. Keep liveness separate from dependency readiness. Do not add a logging platform
  to a single local health endpoint just for completeness.
- Measure time/memory/query plans on representative workloads. Current Olist processing is a local
  in-memory batch; if volume/concurrency increases, benchmark and revise it before promising scale.

## User interface and release gates

- Use semantic HTML, labels, visible keyboard focus, appropriate contrast, responsive layouts,
  accessible error/loading/empty states, and reduced-motion support when animation exists.
  Check small screens, zoom, keyboard operation, and supported browsers as flows are added.
- Public deployment requires validated production settings, HTTPS, reviewed host/CORS/security
  headers, protected secrets/resources, safe errors, data/access review, monitoring, rollback,
  and backup/restore evidence where stateful. `noindex` is not privacy or authorization.
- CI/CD is introduced at the appropriate master-plan stage. Current reproducible local gates
  are mandatory; Phase 10 adds the production automation/observability work. If earlier team
  collaboration makes CI necessary, document that narrow phase adjustment rather than implying
  remote checks exist. Never deploy automatically merely because a build succeeds.
- Before collaborative merges, verify repository rules and required checks are configured for
  the actual branch workflow. Local Git configuration cannot prove GitHub protection settings.

## Verification and exceptions

See [CONTRIBUTING](../CONTRIBUTING.md) for the repeatable checks and review workflow.
The [Phase 1–2 audit](engineering-audit-phase-1-2.md) records current coverage, corrected
issues, and explicit exceptions. Every future phase handoff must carry forward unresolved
items with an owner (the project maintainer), mitigation, and a concrete revisit/release gate.
