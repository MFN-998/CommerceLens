# Post-Phase 3 governance audit

Started 2026-10-05. Status: COMPLETE / VERIFIED; Phase 4 gate PASSED for local exploratory analysis.
Baseline: 6ffe5876fe8ac14193bd2ec19a9e92d52fff112f on feat/warehouse-foundation,
clean and HEAD/upstream 0/0 at recovery. Phases 1-3 remain COMPLETE / VERIFIED.
Methodology: deletion-and-governance.md and engineering-standards.md.
No merge, deployment or paid upgrade. Phase 4 starts only in its separate chat after publication;
resource deletion remains limited to the specific isolated tool boundaries recorded below.

## Milestones and coverage inventory

1. Recover baseline and establish this inventory (complete).
2. Review actual implementation, failure boundaries and tests; record findings.
3. Correct Critical/relevant Important findings in atomic verified units.
4. Run appropriate Phase 1-3 regressions, reconcile debt/docs and publish gate evidence.

| Area | Actual review targets | Completion evidence required | Status |
| --- | --- | --- | --- |
| Architecture/design | api/app; src/ingestion, cleaning, validation, warehouse; dbt models/macros; ADRs 0001-0004 | Boundaries, grains, coupling, abstraction/dependency decisions and finding disposition | Complete; final assessment below |
| Scalability/reliability | loading, migrations, dbt runners, reconstruction, query plans; validation publication/locks | Integrity, bounded resources, concurrency, timeouts, repeat/recovery; Q01 and backup gate carried forward | Complete; final assessment below |
| Workflow/QA | tests, api/tests, conftest, scripts/check.ps1, retained native receipts | Safe offline checks, meaningful regression coverage and explicit unrun/live boundaries | Complete; final assessment below |
| Development lifecycle | CONTRIBUTING, setup, locks, migration checksums, Git/release/handoff | Reproducibility, review, onboarding, rollback and branch-rule limits | Complete; final assessment below |
| DevSecOps/infrastructure | config/credentials, SQL privileges/access, CLI errors, API/web exposure, ignores/locks | Threat review for actual surfaces, secret scans, current advisory evidence; no production certification | Complete; final assessment below |
| Code quality/maintainability | all implementation modules, SQL/macros, tests, typing/lint, unused resources | Readability, duplication, complexity, debt and justified refactor decisions | Complete; final assessment below |
| Product/UX | web/app and configuration, API foundation, source caveats | Current preview semantics/trust/a11y/layout; future interactive gates distinguished | Complete; final assessment below |

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

## G05 - Recommended: stale unproven-budget descriptions

- Location: src/warehouse/dbt_reconstruction.py and reconstruction_acceptance.py
  module descriptions; current contributor/development safety wording.
- Why: descriptions still said fresh-target budgets were unproven despite accepted
  2026-10-05 native receipts; current source-test cleanup warnings were also stale
  after G02. This confuses evidence recovery and safe onboarding.
- Solution/decision: link dated receipts, retain no-guarantee language, and reconcile
  current guides with resource retention and the separately installed patched frontend.
  Implemented immediately; no historical evidence rewritten.
- Side effects/dependencies: editorial only; no budget, target, model, test, access or
  retry behavior change. Architecture unchanged. Ruff/type checks verify source edits;
  local link/diff checks verify documentation. No new native run claimed.

## G06 - Recommended: retained provenance aliases need accurate lifecycle documentation

- Location: src/ingestion/olist.py::acquire uses os.link for atomic no-clobber
  manifest publication; retained .artifacts/olist-acquisition-*/manifest.json.
- Why: after G02 retention, that prepared manifest remains a hard-link alias of the
  canonical source manifest on a newly acquired snapshot. It is immutable provenance,
  not an independently editable draft/backup. Editing either alias changes shared bytes.
- Solution/decision: explicitly document the alias and prohibit treating it as an
  editable/generated draft. Existing raw/hash checks fail closed on changed metadata.
  Preserve the proven no-clobber publication mechanism; do not introduce an unverified
  cross-platform filesystem primitive to eliminate an intentionally retained alias.
- Side effects/dependencies: additional retained metadata/snapshot disk; future archive,
  restore, cleanup or source-version tooling must review identity/link dependencies.
  No backup/PITR claim, and owner approval remains required for resource deletion.
- Architecture: no database/data-grain change; future lifecycle adjustment only if a
  real consumer needs independent copies. Maintainer-owned deferred implementation.
- Verification: acquisition repeat/provenance/tamper/restore regressions pass; current
  source hash verification passed nine files. This audit did not reacquire real Olist.

## G07 - Important: repeat-load identity omits stored manifest checksum

- Location: src/warehouse/loading.py::load_source existing-snapshot SELECT/identity.
- Issue/why: repeat identity compared load ID, source fingerprint, handle, contract
  version and file evidence, but omitted ops.source_loads.manifest_sha256. A newly
  prepared plan could accept changed provenance metadata/bytes with identical CSVs.
- Solution/decision: select and compare the existing manifest hash as part of exact
  identity before reading stored rows. Immediate, implemented; incompatible provenance
  fails closed for review rather than rewriting the registry or reacquiring data.
- Side effects/dependencies: whitespace/metadata changes now also require provenance
  review; canonical manifest must remain byte-identical. No migration, new column,
  permission, load-ID, source row, monetary value, model or architecture change.
- Verification: both whitespace/acquisition-time cases failed before/pass after;
  healthy identical-manifest control passed. Focused source/loader/reconstruction
  suite 93 passed. Final complete offline suite 1652 passed/1000 deliberate native
  skips/one known AnyIO warning in 45.65 s; mypy 27 and Ruff passed.
- Current native correction check: guarded reconstruction load on approved isolated
  histbcmlctxmtxusfbzt returned passed/verified_existing, 1,550,922 rows, raw/database
  275,988,480/287,135,411 bytes. All nine stored text/ordinal/digest/exact-money
  reconciliations and the new registry-manifest comparison completed. No reload,
  migration, original-target operation, credential swap, deletion or dbt rebuild.
  Receipt observation 2026-10-05T05:47:26Z; no elapsed-time guarantee claimed.

## Final seven-area assessment

Review scope is the implemented Phase 1-3 product, not future feature certification.
Source/SQL/configuration review, behavior/failure tests, native receipts and actual
rendering were used together; test counts are not a line/branch-coverage claim.
All findings and retained debt are maintainer-owned. Current corrections preserve
architecture and roadmap. No Critical issue with an applicable current attack/data
corruption path remains; relevant Important G01/G02/G03-runtime/G07 are verified.

| Area | Reviewed behavior and evidence | Assessment and disposition |
| --- | --- | --- |
| Architecture/design | Separate FastAPI/web/data responsibilities; acquisition/cleaning/contracts/profile/publication; warehouse settings/credentials/migrations/source/COPY/dbt/access/reconstruction; ADRs and staging/core/mart SQL | Cohesion and boundaries appropriate for a solo portfolio product. Explicit grains, source lineage, unique ZIP/identity mappings and independent child aggregation avoid fanout. Fixed model/macro allowlists and separate guarded reconstruction are justified safety boundaries, not generic infrastructure candidates. Shared lock retention introduced only for two actual consumers. No service decomposition/ORM/event bus needed. |
| Scalability/reliability | Bounded source hashing/CSV iteration/server cursors; transactional ledger/all-table COPY; advisory locks; registry repeat identity; decimal guards; SQL/lock/idle/job timeouts; one dbt thread/retries zero; capacity ceilings; graph failure preservation | G07 closes repeat provenance gap. Current native repeat reconciled complete stored content with unchanged size. Current Olist batch remains in memory in Phase 2; no higher-volume/concurrent-service promise. Source models are all views under measured capacity constraints. Q01 remains before API workloads; no speculative tuning. Partial dbt graph failure requires explicit inspection, not blind retry. Source reconstruction is not protected backup/PITR. |
| Workflow/QA | Offline API/source/data/warehouse synthetic cases; SQL/model/domain/reconciliation tests; retained tmp_path; runner manifest/invocation/test coverage validation; full gated native reconstruction receipts | G02 restores full deletion-safe Python regression access. Final 1652 passed/1000 deliberate native skips; new G07 current native repeat separately verified. Historical 20/282 builds twice and 42/42 acceptance retained; not rerun wholesale after changes confined to loader repeat identity/filesystem/Next patch. Native empty-target fixtures remain prohibited on populated targets. Patched fresh frontend install/lint/types/build and basic browser checks passed. Future metric/API integration/E2E remains with real flows. No coverage percentage invented. |
| Development lifecycle | Git/status/upstream/history; focused checkpoints; CONTRIBUTING/setup/manifest-lock pairing; migration order/checksums/atomic replay; ADRs; WORK_STATE/recovery; original vs isolated tool installations | Current development and isolated recovery resources remain distinct. No shared branch rewrite/merge/release/deployment. Git/source reconstruction cannot roll back external state. G05 corrects stale evidence/onboarding language. Current original frontend installation is retained at old versions and explicitly excluded from patched-toolchain claims. GitHub required-check/branch-rule state is not verified; E08 gate precedes collaborative merges. |
| DevSecOps/infrastructure | Fixed target/purpose configuration, verified TLS, protected credential creation, SCRAM verifier, restricted jobs/roles/ACLs, narrow mart grant, API CLI safe diagnostics, SQL parameters/identifiers, React output, dependency/secret scans | G01 prevents library details entering tracked reports; G03 patches vulnerable runtime package. Full npm scan still fails on unpatched dev-only braces chain, with bounded trusted-pattern exception. Health-only API has no sensitive/object/state-changing endpoints or database connection; static React preview has no raw-HTML sink, dynamic fetch or image-generation route. Injection/object authorization/RLS/session/CSRF/SSRF/rate-limit review must expand with actual features. Private schemas/API-role denials/Data API off have dated native evidence; no public/ASVS/penetration-test certification. |
| Code quality/maintainability | Implementation modules/macros/models, test layout, gradual dataframe typing, isolated config injection, public boundaries/CLI failure behavior, pattern scan for dynamic execution/raw HTML/TODO/debug, Ruff/mypy and known debt | Ruff checks 165 files; mypy 27 implementation files passed. No eval/exec/pickle/shell=True/raw HTML use found in implementation surfaces searched. Fixed allowlists and independently authored oracles are deliberate rather than DRY refactor targets. Report dictionaries remain gradual (E10), KaggleHub import exception is scoped. G04 keeps retained evidence outside normal frontend source globs. No unjustified abstraction or broad code-reorganization batch. |
| Product/UX | Static page/layout/CSS/icon/metadata and live patched preview at 320/1280; API health/OpenAPI/404/config tests; historical data/source caveats | Current truthful foundation preview is coherent: historical anonymized data, no live feed, no connected analytics/fake KPI/navigation action. One main/h1, English language and labeled section; narrow/desktop screenshots show no horizontal overflow, no captured browser errors. No interactive controls, chart/filter/loading/error/data-delete flow exists yet; build those with Phase 6, including keyboard/focus, contrast/zoom, browser matrix and integrated E2E. Formal accessibility/production readiness not claimed. |

## Carried debt: concrete gates and architectural implications

The original E01-E10 record remains dated historical evidence; the decisions below
are the current disposition. No Optional/Future infrastructure is added merely for
appearance. Full issue context stays in engineering-audit-phase-1-2.md and linked
warehouse/source guides. Verification below distinguishes implemented controls from
unrun future checks. All deferred items have the project maintainer as owner.

| ID / severity, issue and location | Solution / status / gate | Dependencies, side effects and architecture | Verification and current limit |
| --- | --- | --- | --- |
| Q01 Important, views-heavy aggregate latency/spills in warehouse queries | Deferred before Phase 5 API analytics: benchmark actual projections/filters/concurrency/budgets; tune only on measured need | Statistics/indexes/materialization/caching may affect CPU/storage/rebuild overlap under ADR 0004; no change for EDA convenience | Dated 4-9 s cached server samples and grain/results proven; no new latency/SLO/concurrency claim |
| E01 Important bounded tooling exception, ESLint 9 EOL plus G03 dev braces chain | Retain compatible trusted-local linting; recheck when compatible patch/tooling exists, before substantive Phase 6 work and public release | Peer-compatible toolchain/lock update requires fresh lint/types/build; avoid forced peers/downgrade. No product-runtime braces dependency | Fresh patched lint passed; registry/advisory has no braces fix; complete npm scan five high, runtime scan zero |
| E02 Recommended, AnyIO warning in API test tooling | Defer to relevant FastAPI/Starlette/AnyIO upgrade and deployment | Dependency compatibility/regression gate; no blanket suppression or architecture change | One documented warning; API tests and full suite pass |
| E03 Recommended, optional npm resolver install scripts | Scripts remain disabled; review specific script only if actual platform/install needs it | Fresh install/native tooling compatibility; no blanket script permission | Fresh patched ci/lint/types/build work with scripts disabled; no script execution required |
| E04 Recommended, Phase 2 in-memory batch/per-file report publication/interrupted lock | G02 retains output/releases normal locks; scheduling/larger-volume/unattended service still deferred | Transactional report generation/streaming only with real scale/concurrency need; retained outputs use disk and need approved lifecycle review | Success/failure/repeat/concurrency/round-trip tests pass; no multi-file crash-atomic report claim |
| E05 Important downstream source quality/grain gate | Phase 3 controls satisfied; Phase 4 must document exploratory eligibility/limitations; official KPI policy stays Phase 5 | Exact warehouse money, child aggregation, review/geography decisions; no silent record correction/filtering | Historical full native graph/independent checks accepted, current source/repeat verified; 29 warnings retained |
| E06 Recommended stage-dependent recovery/exposure | Private development controls/source reconstruction verified; protected backup/restore before shared irreplaceable state, network/public review before exposure | Recovery retention/protection/restore proof needs actual state requirements; no paid/enterprise/PITR infrastructure introduced | Not populated backup/PITR, consumer auth or public security proof |
| E07 Recommended stage-dependent API/product/security/UX | Add identity/object authorization, bounded payloads/queries, headers/HTTPS/CORS/CSRF where relevant, safe diagnostics/rate limits and integrated UX/E2E with actual flows, before release | Future reader login/session proof, API response minimization (mart includes identifiers), state deletion integrity, deployment rollback, browser/a11y gates | Current API health-only/static UI basic checks pass; no protected-data/public-flow release accepted |
| E08 Recommended lifecycle/CI/branch rules | Verify remote protections before collaborative merge; automation at planned stage or a justified earlier collaboration need | Actual team/release workflow; Git config/local checks do not prove remote protection | Focused published checkpoints/local checks exist; remote CI/protections not certified |
| E09 Optional license choice | Owner selects reuse terms before asserting a software license | Owner decision; dataset attribution/license separate; no invented license text | Code license not selected; no new license grant claimed |
| E10 Recommended gradual dataframe/report typing | Tighten stable shared report contracts when consumers expand; recheck KaggleHub typing on upgrade | Real consumers/runtime dataframe contracts; no broad typing suppression or speculative schema framework | Mypy bodies/API checked, runtime schemas/tests pass; report dictionaries remain gradual |
| Source-date caveat Recommended, Phase 2 pandas loose calendar/special-date parsing | Defer stricter Phase 2 source-version compatibility review before accepting a new snapshot | Current immutable version proven; warehouse fixed grammar/calendar/range guards remain authoritative; no hidden normalization | Current-source hashes/native reconciliation pass; no new source version accepted |
| Coordinate caveat Recommended, text float output formatting | Use binary or reviewed precise representation before future coordinate API use | Public payload/source interpretation and precision review; do not invent canonical ZIP coordinates | Stored/native precision has accepted evidence; extra_float_digits=0 text is not exact representation |
| G06 Recommended, retained manifest hard-link alias | Treat retained alias as immutable provenance; review before future archival/source lifecycle change | Shared inode means not an independent editable backup; retain atomic no-clobber publication, no deletion authorized | Current source unchanged; repeat identity now checks exact manifest hash; tamper/restore regressions pass |

## Resource review and approval record

No new project resource was verified truly obsolete for deletion. Current source,
locks, instruction adapters/icon, ADRs, historical receipts/plans and audit evidence
have an implementation/recovery/review purpose. C fallback/three drafts were already
explicitly retained by owner choice in cleanup-review-2026-10-02.md; that disuse/size
review and approved A/B/D completion remain unchanged. Newly retained test/source
preparations/build/install evidence may become lifecycle candidates after actual use
and dependency review, but are not implicit cleanup targets. Retain both Supabase
projects, datasets, settings/certificates and generated evidence.

Only specifically approved automatic tool cleanup: the isolated frontend snapshot's
.next, node_modules and .npm-cache. No other resource deletion occurred. All copies,
compiler/type outputs, fixture/preparation/released-lock resources and native evidence
remain. Temporary local preview was stopped after checks; browser viewport restored
and temporary tab closed. Legitimate authorized future product data deletion is not
disabled by this project-file retention rule.

## Verified exit and successor handoff

All seven areas are assessed above. Immediate applicable Important corrections and
appropriate Phase 1-3 regressions passed; Recommended findings have explicit
dispositions. The five high development-only npm entries remain an accepted bounded
exception, not a clean full audit. No applicable current Critical blocker remains.
The retained-output exact-password scan passed without logging content or secrets.
See [machine-readable current evidence](governance-audit-verification.json), distinct
from historical native graph receipts. Staged-content and redacted history scans,
whitespace/documentation checks and clean published Git state gate the containing
checkpoint. Resolve its identity through Git history rather than a self-referential hash.

Phase 4 may now begin only in a new local chat using the
[Phase 4 handoff](phase-4-handoff.md). All future exposure, workload, source-version,
backup and release gates remain applicable. No Phase 4 analysis was performed here.
