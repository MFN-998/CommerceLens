# Post-Phase 3 governance audit

Started 2026-10-05. Status: IN PROGRESS; Phase 4 gate NOT PASSED.
Baseline: 6ffe5876fe8ac14193bd2ec19a9e92d52fff112f on feat/warehouse-foundation,
clean and HEAD/upstream 0/0 at recovery. Phases 1-3 remain COMPLETE / VERIFIED.
Methodology: deletion-and-governance.md and engineering-standards.md.
No merge, deployment, paid upgrade, resource deletion or Phase 4 work authorized.

## Milestones and coverage inventory

1. Recover baseline and establish this inventory (complete).
2. Review actual implementation, failure boundaries and tests; record findings.
3. Correct Critical/relevant Important findings in atomic verified units.
4. Run appropriate Phase 1-3 regressions, reconcile debt/docs and publish gate evidence.

| Area | Actual review targets | Completion evidence required | Status |
| --- | --- | --- | --- |
| Architecture/design | api/app; src/ingestion, cleaning, validation, warehouse; dbt models/macros; ADRs 0001-0004 | Boundaries, grains, coupling, abstraction/dependency decisions and finding disposition | Pending detailed review |
| Scalability/reliability | loading, migrations, dbt runners, reconstruction, query plans; validation publication/locks | Integrity, bounded resources, concurrency, timeouts, repeat/recovery; Q01 and backup gate carried forward | Pending detailed review |
| Workflow/QA | tests, api/tests, conftest, scripts/check.ps1, retained native receipts | Safe offline checks, meaningful regression coverage and explicit unrun/live boundaries | Pending detailed review |
| Development lifecycle | CONTRIBUTING, setup, locks, migration checksums, Git/release/handoff | Reproducibility, review, onboarding, rollback and branch-rule limits | Pending detailed review |
| DevSecOps/infrastructure | config/credentials, SQL privileges/access, CLI errors, API/web exposure, ignores/locks | Threat review for actual surfaces, secret scans, current advisory evidence; no production certification | Pending detailed review |
| Code quality/maintainability | all implementation modules, SQL/macros, tests, typing/lint, unused resources | Readability, duplication, complexity, debt and justified refactor decisions | Pending detailed review |
| Product/UX | web/app and configuration, API foundation, source caveats | Current preview semantics/trust/a11y/layout; future interactive gates distinguished | Pending detailed review |

## Finding format and severity

For every finding record: ID; issue and exact location; why it matters; severity;
recommended solution; side effects; dependencies; architectural implications;
immediate/deferred decision and concrete revisit gate; exact verification/status.
Critical blocks continuation. Relevant Important precedes Phase 4. Recommended is
assessed individually. Optional/Future infrastructure requires actual need.

## Recovery observations and verification safety

Read AGENTS, WORK_STATE, master plan, engineering standards, execution protocol,
deletion/governance, Phase 3 status and final reconstruction receipt before edits.
Inspected Git status/history and confirmed clean baseline/upstream equality.
Final native receipt: nine tables/1,550,922 rows, two 20-view/282-test builds,
42/42 independent cases, preserved reader ACL/identity and private access denials.
This is historical native evidence dated 2026-10-05, not a new execution in this audit.

scripts/check.ps1 is not safe to run unchanged under the permanent deletion rule:
acquisition tests explicitly unlink/rmtree fixture resources; validation uses a
TemporaryDirectory and lock/temp cleanup; frontend build/type generation needs
its own reviewed retention workflow. conftest overrides tmp_path to retain UUID
fixtures, but that does not prevent explicit test/tool deletion. Review execution
paths before tests; use static checks and non-deleting subsets first. Do not replace
cleanup with destructive overwrites or bypass isolated native tooling.

Retain C fallback/three drafts, both Supabase projects, protected settings/CA,
datasets and generated evidence. Potential obsolete resources need reference/use
verification and specific informed approval before removal.

## Carried-forward gates

Q01 remains Important before actual API analytics: dated cached 4-9 s queries,
spills/estimate errors; no speculative indexes/materializations/caching.
E01-E10 retain staged revisit gates from engineering-audit-phase-1-2.md; E05's
Phase 3 controls are verified, E06's protected backup/restore remains before
shared irreplaceable state. Future reader login/authentication, source/date and
coordinate output caveats remain visible. Source reconstruction is not backup/PITR.
CI/branch protection, interactive E2E/a11y, public security and deployment are not
claimed. Audit exit requires actual coverage, required corrections and regressions.

## Account-wide usage

At recovery: 65% five-hour and 57% weekly remaining. Not a task reservation or cost
prediction. Check before each major unit and preserve checkpoints before exhaustion.

Initial static checks (2026-10-05): Ruff lint passed, format checked 162 files,
mypy passed all 26 implementation files. No full regression claim yet.

## G01 - Important: exception details in tracked Phase 2 reports

- Location: src/validation/run.py::_run, per-table source_read and outer
  integrity_or_staging exception handlers; tests/test_validation_diagnostics.py.
- Issue/why: arbitrary library exception messages were copied into JSON/Markdown
  reports committed as aggregate evidence. Conversion, I/O or profiling errors
  can contain input values or local paths, defeating the report privacy boundary.
- Recommendation/decision: fixed contextual diagnostics; preserve table/check,
  severity, blocking count and failed promotion. Immediate, implemented.
- Side effects: reports no longer expose raw library diagnostics; local source
  contracts/provenance and retained snapshots support investigation. Existing NUL
  regression now checks the structured failed table/check, not exception wording.
- Dependencies/architecture: no dependency, database, successful-data conversion,
  grain, money or architecture changes. No resource deletion.
- Verification: 12 synthetic regression cases failed before correction and passed
  afterward; covers ValueError/OSError/TypeError at read/profile/provenance/staging
  boundaries and all three report outputs. API + regression subset: 20 passed.
  Retained broad offline suite: 1590 passed, 1000 deliberate live skips, one known
  AnyIO warning, 43.84 s. Acquisition/legacy validation modules excluded pending
  their deletion-safe workflow; native opt-ins removed, no live database claims.
  Mypy passed 26 implementations. Ruff found one long diagnostic line, shortened
  before checkpoint. Frontend format passed; lint completion still being checked.

## G02 - Important: required regression workflow conflicts with resource retention

- Location: src/ingestion/olist.py temporary/lock cleanup;
  src/validation/run.py temporary snapshot/report/lock cleanup;
  tests/test_acquisition.py explicit unlink/rmtree; scripts/check.ps1 frontend tools.
- Why: the permanent owner rule forbids unapproved indirect deletion. Current
  documentation warns against full checks but leaves required Phase 2 regressions
  unavailable without additional deletion approval.
- Recommendation: preserve temporary snapshots, failed report files and released
  locks, preserve deliberately missing synthetic fixtures by bounded moves, and
  review fresh isolated frontend output paths. Do not suppress tests or intercept
  deletion globally. Implement and verify a small retention correction separately.
- Decision: immediate pending; blocks audit regression exit until resolved or a
  specifically approved bounded alternative exists.
- Side effects: increased ignored local disk use; list retained artifacts and seek
  exact deletion permission only when justified. Dependencies: acquisition and
  validation failure/replay/concurrency tests; frontend tooling review.
- Architecture: local filesystem lifecycle only; no database/product deletion,
  source contract, infrastructure or business-policy change is required.
- Verification: pending implementation/failure/repeat/concurrency regressions.

### G02 Python retention correction - verified 2026-10-05

Implemented local retention in src/retention.py and acquisition/validation lifecycle:
released locks move to unique siblings; failed/completed preparation outputs stay;
failed report publication keeps the old report and prepared temporary file. Synthetic
missing-file/restore tests move fixtures to retained paths instead of deleting them.
No blanket deletion interception, test disabling or product/database deletion change.
The helper is shared because both existing batch tools need the same lock lifecycle.
Added four tests for repeat evidence preservation, boundary refusal and failed move.
Existing concurrency/protected snapshot/failure/repeat tests pass. Ignored failed
report fragments exclude generated evidence from accidental staging.

71 focused checks passed; complete plugin-isolated offline suite: 1649 passed,
1000 deliberate native skips, known AnyIO warning, 46.75 s. Mypy: 27 implementations
passed. No native source load/rebuild is needed for this filesystem-only change;
complete recorded native Phase 3 evidence retains its date. Frontend format/lint
passed on the unchanged installed toolchain. The original full script still needs
a safe frontend snapshot; G02's frontend portion remains pending.

Owner explicitly approved build-tool cleanup only inside
D:\My Projects\CommerceLens\web\.artifacts\governance-20261005-01\.next.
The retained tracked-source snapshot contains no private environment/dataset/old build.
No deletion outside that boundary is authorized, including dependency installation.

## G03 - Important: currently vulnerable frontend dependency versions

- Location: web/package.json, package-lock.json, installed toolchain.
- Current scan: npm reports Next 16.3.5 affected by critical
  [GHSA-vcvr-r3jv-pc5j](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j),
  fixed from 16.3.6. Registry verified compatible patch 16.3.8 and matching ESLint
  config. Current app has no next/og ImageResponse or attacker-controlled SVG
  rendering; no deployed service. Project severity Important, immediate patch.
- Separate lint-only chain: braces <=3.0.3 affected by high
  [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm),
  propagated through micromatch/fast-glob/Next lint config (five high packages).
  Registry latest braces remains 3.0.3; no verified patched release available.
- Recommendation: exact compatible Next/config patch; no forced Next 14 downgrade
  suggested by npm and no fabricated braces override. Evaluate lint-only trusted
  repository-pattern exposure separately with E01 before substantive frontend work.
- Side effects/dependencies: lock consistency, fresh isolated install and full
  frontend type/build/lint verification. Existing node_modules must remain intact
  without specific deletion approval. No React/business/UI architecture change.
- Status: patch pending. Lint-chain bounded exception needs final disposition.
- Verification: current npm scan FAILED (1 critical/5 high); Python pip-audit
  passed 111 installed packages, zero findings/skips. These replace dated advisory
  observations only for their current tool scope, not production certification.

### G03 dependency correction - verified 2026-10-05

Next and matching eslint-config-next pinned to 16.3.8; reviewed lock changes cover
Next env/plugin/platform SWC packages and npm's previously omitted optional WASM
metadata. No forced major downgrade, install scripts or React upgrade. Fresh isolated
npm ci installed 359 packages with scripts disabled; actual Next version 16.3.8.
Owner separately approved tool cleanup only in that snapshot's node_modules and
.npm-cache, alongside the previously approved .next. Original web/node_modules,
web/.next and every earlier artifact remain retained. They are not silently refreshed:
use the verified isolated installation until any future original-install replacement
has the required specific approval. No merge or deployment occurred.

Patched lint, next typegen/strict tsc and production build passed. Static routes:
/, /_not-found, /icon.svg. Snapshot build warns that its nested lockfile causes root
inference to select the outer web lock; source/output paths remain the isolated
snapshot, and its build/runtime version is verified 16.3.8. This warning is not a
production tracing/standalone deployment certification. No config workaround added.
Format check passed. Full npm audit now has zero critical/five high entries;
production-only npm audit has zero findings. npm ls verifies all five high entries
trace only eslint-config-next -> Next lint plugin -> fast-glob -> micromatch ->
braces 3.0.3. Advisory explicitly has no patched version; registry latest is 3.0.3.

G03 runtime correction COMPLETE. Lint-chain disposition: Important bounded tooling
exception, maintainer-owned; accepted for trusted local repository patterns during
Phase 4 EDA, not for untrusted pattern processing or public service exposure. No lint
package is a product-runtime dependency. Recheck on a patched release, toolchain
upgrade, substantive Phase 6 frontend work and before public release (with E01).
Do not claim that the full dependency scan is clean or silently suppress its exit.

## G04 - Recommended: retained frontend artifacts enter normal source checks

- Location: web/tsconfig.json, eslint.config.mjs, .prettierignore.
- Issue/why: retaining an isolated source/build snapshot under web/.artifacts could
  cause broad TS/lint/format globs to inspect duplicate generated evidence as app code.
- Recommendation/decision: explicitly exclude .artifacts in all three tools;
  implemented immediately as part of the isolated verification workflow.
- Side effects/dependencies: ignored evidence is outside application inputs; tracked
  app/config files continue to be checked. Patched snapshot contains matching rules.
- Architecture: no application/runtime/data change or additional tooling.
- Verification: formatting, patched lint, strict types and build passed; source-level
  include/exclude reviewed. No exclusion of tracked application files.

### Current UX verification - 2026-10-05

Reviewed static source and rendered patched snapshot with Codex in-app Chromium:
320x800 and 1280x800 viewports; full narrow screenshot and desktop screenshot inspected.
Document scroll widths 305/1265 versus viewports 320/1280: no horizontal overflow.
English language, meaningful title, one main and one h1, ordered h2/section labeling.
Clear preview/not-connected/historical-anonymized-data/no-live-feed copy; no fake KPIs.
Zero forms/interactive controls, hence current focus/keyboard/destructive-action flows
are not applicable. No captured warn/error browser logs. No animation/reduced-motion
requirement. This is basic semantic/layout verification, not formal WCAG conformance,
zoom testing, all-browser certification or future dashboard/API E2E acceptance.

Current read-only source verification passed all nine immutable files. Offline dbt
parse passed with fresh retained artifacts .artifacts/dbt/97ccd72fddb741ecac7d859e79ad17bf.
No database connection/load/model build/grant change ran in this audit.
