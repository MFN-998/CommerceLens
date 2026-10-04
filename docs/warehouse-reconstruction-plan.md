# Populated warehouse reconstruction plan

Phase 3 M5. Full-graph runner source/offline verification COMPLETE.
**LIVE RECONSTRUCTION NOT EXECUTED; populated proof remains pending.**
The accepted CommerceLens Supabase target, source files, private configurations,
certificates and retained artifacts stay protected. This plan reconstructs the
development warehouse from immutable source and versioned code; it does not prove
a populated backup restore, point-in-time recovery or future reader-login security.

## Prepare locally before requesting a target

1. Complete the remaining isolated configuration/orchestration work around the
   verified full-graph runner. The broader reconstruction workflow uses the exact twenty
   approved views. The normal single-model CLI uses eager indirect tests; from an
   empty graph these can reference children not yet constructed. Use the verified
   full-graph callable below and verify exact model/test manifests and the complete
   enabled tests once dependencies exist.
   Do not bypass the runner, suppress failing tests or weaken existing acceptance.
2. Test isolated configuration dispatch for admin, loader and transformer, verified
   certificate paths, retained artifact directories, target identity and failure/retry
   handling. Every operation must match the approved fresh project reference and
   reject the protected current target. No fallback to current credentials or paths.
3. Preserve fixed roles, verify-full TLS, one thread, zero retries, bounded job/SQL
   timeouts, safe diagnostics and secret-free artifacts. Review any whole-graph job
   budget separately; the existing 180-second one-model budget is not a full-graph promise.

Local database/container tools are unavailable in the feasibility assessment.
An alternate engine would require an adapter and separate proof of native money,
timestamp, role/ACL and dbt behavior. A fresh native Supabase Free project therefore
requires the least additional tooling if it is available and eligible.

## Guarded full-graph source unit — 2026-10-04

`src.warehouse.dbt_reconstruction.run_dbt_graph(command, *, settings_root,
expected_project_ref)` is a separate callable for `build` or `test` only. It keeps
code/project/profile paths fixed, leaves the accepted one-model wrapper unchanged,
and accepts no caller selector, SQL, materialization, profile or flags. It is not
yet exposed as a CLI and does not orchestrate migrations/loading/provisioning/grants.

The explicit settings directory must exist outside the code repository and cannot
contain that repository. Load only its transformer purpose file, require test
environment and the expected native project identity, reject the protected
`imvahwzlovgmaltuysmb` target and all ambient WAREHOUSE overrides. The resolved
purpose file, CA and UUID artifact paths must remain inside that isolated directory;
there is no fallback to accepted credentials or certificates.

Synthetic offline parse precedes live dispatch. The graph requires exactly twenty
approved view names/aliases/schemas, nine raw/postgres sources and all enabled
blocking tests with zero-failure thresholds and no failure storage/filter/limit.
Reject unexpected executable resources, disabled nodes, hooks and wrong references.
Require the reviewed preserving-view macro's pinned definition and all six local
macro definitions; missing/changed override cannot silently activate dbt's normal
backup/cleanup behavior. Compare code, checksums, config, columns and relation
dependencies between preflight/live; compilation-added macro dependency lists are
excluded because they legitimately grow. Macro definitions remain compared.

Build requires every approved view success and every enabled test pass/zero failures;
test requires every enabled test pass/zero failures without asserting model builds.
Reject missing/extra/duplicate/failed/warned/skipped/stale-invocation evidence, even
after subprocess zero exit. The current accepted graph has 20 views and 282 tests.

One thread, zero retries, verify-full TLS, existing dedicated capability and
SQL60s/lock10s/idle60s remain fixed. Parse budget120s; whole graph budget1200s
is a conservative upper bound, **unproven on a fresh Free target**, not a completion
promise or consumer latency target. Builds commit views incrementally; failure or
timeout requires reconnect/inspection, retained artifacts and explicit continuation,
without automatic DROP, full refresh, cleanup, credential replacement or source reset.
Artifacts remain under settings_root/.artifacts/dbt-reconstruction/UUID, separately
in preflight/target and live/target. Startup/configuration errors are fixed and safe.

Actual source validation: focused recovery/existing-runner 173 passed in 23.87s;
retained warehouse/API 1481 passed in 38.24s with 1000 deliberate live skips.
Ruff lint/format 156 files and mypy24 implementation files passed.
Network-blocked real parsing verifies the unmodified graph; subsequent result
evidence in that test is explicitly simulated, not a native build. A separate dated
read-only comparison against the retained accepted build manifest matched the
real preflight model/test/source contracts after excluding runtime macro-list growth.
Initial sandbox execution could not create retained fixture directories; the approved
rerun passed. No source-test failure remained. No accepted private credentials,
warehouse data or live graph were used for this unit.

**Still required before target approval:** isolated admin/loader/transformer
configuration dispatch, CA/credential protection, migration/load/provision/grant
guards and failure/retry orchestration. Do not run existing ROOT-based CLI commands
with a presumed alternate target or create the hosted target before that preparation.

## Concrete target approval, after local preparation

Check current Free-project eligibility, organization quota and capacity before
requesting approval to create **one isolated reconstruction project**. No current
eligibility, paid plan or project creation is assumed or authorized by this draft.
The approval must identify the new target, intended source upload and retention.
If Free is unavailable, stop and present a reviewed alternative before proceeding.

Use separate protected configuration files for all three purposes, a separate CA
certificate path and separate artifact roots. Never replace the accepted target's
files, environment or artifacts. Privately configure the approved target from its
actual connection details; preserve hostname verification and private schema/API
boundaries. Target creation does not authorize deleting either project afterward.

## Exact construction and verification order

1. Verify the fresh isolated target/version, empty warehouse state, private API
   exposure and initial capacity. Apply unchanged `0001_foundation.sql`, then
   `0002_source_landing.sql`; verify ledger checksums and unchanged replay.
2. Provision target-specific restricted loader and transformer job logins using
   reviewed tooling and protected files. Reader remains the NOLOGIN capability;
   create no reader login or credentials.
3. Prepare the existing immutable source manifest/hashes and deterministic load
   identity. Load all nine source tables with the restricted loader and complete
   text/ordinal/content-digest/count/exact-money reconciliation before acceptance.
   Reconnect and repeat the same load: require `verified_existing`, the same load
   identity and hashes, unchanged registry/source contents and no duplicate snapshot.
4. Construct the twenty unchanged views in this valid dependency order:
   - Nine staging views: `stg_customers`, `stg_sellers`, `stg_category_translation`,
     `stg_products`, `stg_orders`, `stg_order_items`, `stg_order_payments`,
     `stg_order_reviews`, `stg_geolocation`.
   - Five dimensions: `dim_location`, `dim_customer`, `dim_product`, `dim_date`,
     then `dim_seller` after `dim_location`.
   - Mapping: `int_order_customers`.
   - Four facts: `fact_orders`, then `fact_order_items`, `fact_payments`, `fact_reviews`.
   - Mart: `mart_order_components`.
   Verify every enabled model/test result through the prepared workflow; all twenty
   views and complete source/grain/domain/reference/multiset checks must pass.
5. Apply the fixed post-model `grant-mart-reader` step only after the mart exists.
   Verify effective reader SELECT and source/write/API/PUBLIC/off-target denials.
   Repeat the grant and a compatible mart rebuild; prove unchanged identity,
   ownership, ACL and default privileges.
6. Reconnect for independent physical/source/model/per-order reconciliation and
   technical-query checks. Record aggregate receipts, full result coverage, native
   types, lineage, retained warnings, access, sizes and artifact secret checks.
   Accept reconstruction only after all gates pass; preserve failed attempts.

## Capacity and failure gates

The first load requires database size **at most 33,000,000 bytes** because the
loader reserves the full raw ceiling before COPY. Actual raw tables/indexes/TOAST
must remain at most **367,000,000 bytes**, and database size at most
**400,000,000 bytes**. Measure before loading, before commit and after graph build.
Keep all models as views. Database size alone does not establish WAL/temp headroom.

After an uncertain commit, reconnect to the approved target and verify stored
state before retrying. Failed COPY can retain allocated space despite rollback;
stop and remeasure rather than bypass capacity checks. No automatic DROP, TRUNCATE,
reset, artifact cleanup or source replacement belongs to this workflow.

The existing loader's deterministic reconciliation/repeat behavior is already
verified on the accepted target. This proposed fresh-target run would add the
missing complete populated reconstruction evidence. Phase 3 handoff and its
subsequent governance gate remain separate completion steps.
