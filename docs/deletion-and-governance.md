# Deletion safety and Phase 3 governance gate

Permanent owner requirements adopted 2026-09-25; recorded 2026-09-27.
They supplement the master plan and engineering standards without redesigning the roadmap.

## Explicit approval before development/project resource deletion

Never delete any development/project file, directory, artifact, configuration, dataset, database-related
file, generated output, documentation, script, source, environment, backup or other resource
without specific owner permission after explaining the proposed deletion. This applies even
to obsolete, duplicate, unused, temporary or regenerable resources. Broad cleanup, refactor,
optimization, technical-debt or production-readiness requests are not deletion permission.
Apply this operating constraint across current/future work wherever these instructions apply.

Before asking, explain: (1) exact names/paths or clearly bounded groups; (2) why deletion is
proposed; (3) disadvantages of keeping them; (4) current use; (5) dependencies; (6) recovery
or regeneration; (7) affected functionality/configuration/history/data/workflow; (8) replacement;
(9) safer alternatives such as retention, exclusion, archive, rename or backup; and (10) the
consequences of declining. Prefer a reversible alternative when deletion is not essential.

Check indirect deletion by test/build/package/database tools too. Automatic cleanup is not
exempt. Do not run a command known to clear artifacts, caches, test directories or development artifacts
without a safe non-deleting configuration or the specific approval above. Retain new artifacts
by default; never replace deletion with an equally destructive overwrite as a workaround.

## Owner clarification: product behavior and ongoing cleanliness

The permission rule governs development/project files and folders, including local files,
generated repository artifacts, project datasets, backups and configurations. It must never
disable or weaken legitimate application deletion: accounts/businesses, feedback/reports,
records/uploads, dashboard items, authorized administration, retention/cleanup or other
intentional product data-deletion behavior. Implement those normally under the product's
authorization and ownership model, confirmations/warnings where warranted, referential
integrity, deliberately designed cascades, appropriate soft/hard deletion, auditability,
privacy obligations and justified recovery/retention. This is not blanket authorization
for the development agent to delete project resources or arbitrary database records.

Keep the repository understandable: actively identify obsolete, unused, replaced, duplicate,
experimental/debug, superseded or unnecessary generated files during ordinary work. Verify
references/dependencies and explain how disuse was checked, what each resource contains,
why removal improves maintenance, affected behavior, replacement, recovery and safer options.
Then ask for specific permission; remove only approved resources and verify afterward.
If declined or unanswered, retain and record them explicitly rather than silently forgetting.
For refactors, create/verify the replacement first, check dependencies/tests, then explain
and request removal of the old resource. Do not perform a broad audit prematurely.

## Required gate after Phase 3, before Phase 4

Do not perform this comprehensive audit until Phase 3 is complete and functionality verified.
Before Phase 4, audit architecture/design; scalability/reliability; workflow/QA; development
lifecycle; DevSecOps/infrastructure; code quality/maintainability; and product/UX.

Cover component boundaries, cohesion/coupling, justified abstractions/dependencies, DRY/KISS
and appropriate SOLID; query/index/API/data efficiency, concurrency/timeouts/retries/idempotency,
fault isolation/recovery/integrity/backups/resource limits; unit/integration/API/database/UI/E2E
and data/regression tests, isolation, coverage where meaningful, lint/types/reproducibility/CI;
Git/review/onboarding/ADRs/configuration/environments/migrations/releases/rollback; secrets,
access control/RLS, input/output validation, injection/XSS/CSRF/SSRF as applicable, supply chain,
headers/CORS/logging/errors, deployment, observability and OWASP-aligned threat review;
readability, complexity, duplication, dead/debug code, typing and debt; navigation, flows,
feedback/loading/empty/error states, accessibility, responsiveness/browser compatibility,
dashboard clarity, perceived performance, user trust and accidental destructive actions.

For every finding record issue/location, rationale, severity, recommended solution, side
effects/dependencies, whether architecture changes are needed, fix/defer decision and exact
verification. Critical issues block continuation; relevant Important issues normally precede
Phase 4; evaluate Recommended changes individually; defer unjustified Optional/Future work.

Fix Critical and relevant Important issues, run regression checks after significant changes,
verify Phases 1–3, update documentation and record accepted debt before Phase 4. No deletion
is authorized by an audit finding. Do not add enterprise infrastructure without actual need.
From Phase 4 onward, apply these seven areas continuously during significant implementation
and architectural decisions, with practical scale, security, maintainability and good UX.
