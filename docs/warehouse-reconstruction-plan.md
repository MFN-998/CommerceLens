# Populated warehouse reconstruction plan

Phase 3 M5 draft. **NOT EXECUTED; reconstruction proof remains pending.**
The accepted CommerceLens Supabase target, source files, private configurations,
certificates and retained artifacts stay protected. This plan reconstructs the
development warehouse from immutable source and versioned code; it does not prove
a populated backup restore, point-in-time recovery or future reader-login security.

## Prepare locally before requesting a target

1. Review and checkpoint a bounded reconstruction workflow against the exact twenty
   approved views. The current runner permits one selected model with eager indirect
   tests; from an empty graph these can reference children not yet constructed.
   Prepare a dependency-safe full-graph or bounded batch path, verify exact model/test
   manifests, and run the complete enabled tests once their dependencies exist.
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
