# Populated warehouse reconstruction plan

Phase 3 M5. Full-graph runner and isolated-operation dispatcher source/offline
verification COMPLETE; final-check adapter also verified offline.
**LIVE RECONSTRUCTION NOT EXECUTED; populated proof remains pending.**
The accepted CommerceLens Supabase target, source files, private configurations,
certificates and retained artifacts stay protected. This plan reconstructs the
development warehouse from immutable source and versioned code; it does not prove
a populated backup restore, point-in-time recovery or future reader-login security.

## Prepare locally before requesting a target

1. Use the verified isolated-operation dispatcher around existing helpers and the
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
and accepts no caller selector, SQL, materialization, profile or flags. The callable
itself does not
orchestrate migrations/loading/provisioning/grants; the fixed dispatcher below
provides one-step CLI access without changing this runner or its accepted counterpart.

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

## Isolated-operation dispatcher — 2026-10-04

`src.warehouse.reconstruction.run_reconstruction_step(step, *, settings_root,
expected_project_ref)` dispatches exactly one fixed operation around existing
helpers. No pipeline engine, new SQL/model, dependency or configuration fallback
is introduced. Code, migrations, immutable source and mart grant SQL remain fixed
in the CommerceLens repository. Only private settings, CA and graph artifacts
belong to the separate settings directory.

| Step | Required purpose | Action |
| --- | --- | --- |
| inspect | admin | Restricted aggregate operational metadata |
| migrate | admin | Apply pending unchanged checksummed migrations |
| verify | admin | Transactional foundation privilege checks; fixtures rolled back |
| provision-loader | admin | New restricted loader login and protected local purpose file |
| provision-transformer | admin | New restricted transformer login and protected local purpose file |
| load | loader | Full immutable source verification/load or deterministic verified repeat |
| dbt-build-graph | transformer | Fixed twenty-view/full-enabled-test build |
| dbt-test-graph | transformer | Full enabled tests without model rebuild |
| grant-mart-reader | transformer | Fixed post-model mart-only SELECT grant |

Require an existing settings directory outside the code repository, test
environment and exact explicit fresh reference, rejecting the protected project.
Every purpose file is contained, regular, singly linked and protected before
reading settings; hard-link aliases cannot trigger permission changes outside the root;
provisioning rejects an existing credential destination without replacing it.
The CA resolves inside the isolated root and becomes absolute for existing native
helpers, preventing their normal repository-root resolution from selecting an old CA.
Reject all ambient WAREHOUSE_* and PG* variables before private-file or connection
work. libpq can use hostaddr to choose a different network address even with an
explicit hostname; see [PostgreSQL connection parameters](https://www.postgresql.org/docs/17/libpq-connect.html).
Do not weaken hostname verification or silently clear the user's environment.

Prepare the complete source plan and migration files before opening the relevant
connection. Existing transactional identity, content/digest, monetary, replay,
capacity and least-privilege checks stay in their original helpers. Return only
an allowlisted receipt after the connection/provision/build context exits cleanly;
driver/configuration details, source records and passwords are not printed.
An error or interruption may leave committed views, a completed load with an
uncertain acknowledgement, or a saved private file. Reconnect and inspect before
the next explicit step: there is no automatic retry, DROP, reset or deletion.

CLI example, **only after a fresh target and upload/retention have been approved**:

```powershell
Set-Location 'D:\My Projects\CommerceLens'
# Replace FRESH_PROJECT_REF with the actual approved target reference; never a password.
.venv/Scripts/python.exe -B -m src.warehouse.reconstruction inspect --settings-root 'D:\My Projects\CommerceLens-Reconstruction' --expected-project-ref FRESH_PROJECT_REF
```

The isolated settings path now exists; the actual approved fresh reference is
`histbcmlctxmtxusfbzt`. All examples require that verified reference.
Change only the fixed step argument after verifying each receipt. Missing or unknown
arguments fail safely; no selector/custom SQL/profile options are accepted.

Actual validation: focused dispatcher/configuration/credentials/existing runners
293 passed in 27.24s; retained warehouse/API 1534 passed /1000 deliberately skipped
live tests in 37.97s. After review's hard-link correction, all54 dispatcher tests
passed in0.44s, including a real linked-file regression. Ruff lint/format158 files
and mypy25 implementations passed again. Scoped review confirmed the correction.
Tests simulate dispatch and failure outcomes; they do not prove fresh native
authentication, migrations, loading or full-graph execution. Existing native
integration tests normally load accepted ROOT settings: do not invoke them against
the fresh target by swapping original credentials or global environment overrides.
Use the verified final-check adapter below to reuse independent acceptance; never
enable empty-landing fixture suites after the populated load.

## Isolated final-check adapter — 2026-10-04

`src.warehouse.reconstruction_acceptance.run_reconstruction_acceptance(*,
settings_root, expected_project_ref)` validates the same isolated admin/transformer
files and launches one fixed Python process. Its allowlist is all twenty physical
built-model modules, the native query-example module and the reader module.
Actual safe collection verified **42 cases across 22 files**: 25 physical, 11
native query and six reader checks. Collection executed no fixtures or test bodies.
Module-local settings bindings are replaced before fixtures; connection routines,
read-only transactions, SQL and independent oracles remain unchanged.

These final checks complement the loader's full content/ordinal/exact-money
verified repeat and the full-graph runner's twenty models/all 282 enabled tests.
They do not repeat the already accepted native boundary matrices or empty-target
bootstrap/COPY fixtures. Inspect the new server version before construction;
prior boundary evidence is PostgreSQL17, so a different version requires reviewed
boundary re-evaluation. Existing query-plan measurements and Q01 remain separate
dated evidence; this adapter does not generate fresh performance claims or plans.

The worker enables only its fixed COMMERCE opt-ins and disables inherited pytest
plugins/options, conftest, cache and output capture. Python isolated mode fixes
the code import root; stdout/stderr go to the null device. It rejects static or
dynamically requested temporary fixtures and an existing/symlink basetemp. Fresh
UUID artifacts remain under settings_root/.artifacts/reconstruction-acceptance.
Atomic receipts contain only target reference, file counts and overall outcomes.
Every collected case needs unique successful setup/call/teardown; missing files,
duplicates, skips, xfails, failed reports, incomplete receipts or nonzero process
exit cannot appear successful. No driver output/source values are retained.
The 600s process budget is unproven on the fresh target; preserve incomplete or
failed receipts and inspect the failure before any explicit rerun. No auto retry
or artifact cleanup occurs. This is a final verification tool, not a backup restore.

CLI after populated graph/grant acceptance:

```powershell
.venv/Scripts/python.exe -B -m src.warehouse.reconstruction_acceptance --run --settings-root 'D:\My Projects\CommerceLens-Reconstruction' --expected-project-ref FRESH_PROJECT_REF
```

Actual offline validation: adapter+dispatcher 97 passed in 0.82s; retained warehouse/API
1578 passed in 43.26s, 1000 deliberately skipped live checks and the known AnyIO
deprecation warning. Ruff lint/format 160 files and mypy 26 implementations passed.
Scoped review found no blocker. These offline tests simulate subprocess/pytest
outcomes; **the native 42-case run and populated reconstruction are NOT YET RUN**.
Local dispatch/full-graph/final-check preparation is complete. Resource approval,
private admin configuration and the native read-only preflight now passed;
unchanged migrations are next. Do not reimplement the verified tooling.

## Approved target and native preflight — 2026-10-04

Owner specifically approved one CommerceLens-Recovery Free/Tokyo project, Data API
disabled, all nine unchanged source tables/1,550,922 rows and retention. The owner
entered the new password and submitted creation, then saved it privately in the
separate admin file. No paid upgrade or deletion of either project is authorized.
Actual dashboard confirms CommerceLens FREE, Tokyo/Nano, reference
`histbcmlctxmtxusfbzt` and Enable Data API OFF/no schemas queryable.

Separate settings root: `D:\My Projects\CommerceLens-Reconstruction`.
Protected `.env.warehouse` uses test/admin, the actual direct host
`db.histbcmlctxmtxusfbzt.supabase.co`, port5432/database postgres/user postgres.
Its public CA is `.credentials/supabase-ca.crt`; observed official dashboard URL
and verified SHA256 `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`
match the trusted published CA. Initial Python HTTPS preparation stopped before
file creation; existing empty directories were retained, Windows HTTPS download
succeeded, and exclusive creation/protection completed without replacement/deletion.
No private content or connection string is recorded here or in Git.

[Native preflight receipt](warehouse-reconstruction-preflight.json) passed at
2026-10-04T18:56:52Z on source checkpoint ed52929: PostgreSQL17.11/170011,
session/current user and database postgres, verify-full TLS active, all five
warehouse schemas absent, all six warehouse capability/job roles absent,
zero warehouse defaults, ledger absent and database10,491,571 bytes (below33M).
Read-only checks changed no database objects. Original settings/target remain intact.

Scoped review of the official [17.11](https://www.postgresql.org/docs/17/release-17-11.html),
[17.10](https://www.postgresql.org/docs/17/release-17-10.html),
[17.9](https://www.postgresql.org/docs/17/release-17-9.html),
[17.8](https://www.postgresql.org/docs/17/release-17-8.html) and
[17.7](https://www.postgresql.org/docs/17/release-17-7.html) patch notes did not
identify a need to redo Phase3's full parser/boundary matrices. This is a scoped
inference, not blanket version certification. Stored-expression type privileges
will be exercised by the restricted native build; existing Decimal/oracle checks
cover relevant money behavior. Fixed numeric dates/naive timestamps and literal C
collations do not use the changed localized date/SQL-JSON/money-type or
nondeterministic-collation paths. Require migrations/permissions/build/42 native
checks to pass on this actual patch; investigate any new failure before proceeding.

Native migrations, role provisioning, source loading, graph construction and final
acceptance are **NOT YET RUN** on this recovery target. Loader and transformer
purpose files are not yet created. Preserve failed attempts; no fallback to original
credentials, no ambient routing, no weaker TLS and no automatic retry/cleanup.

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
