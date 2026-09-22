# Source loading and recovery

This is Phase 3 M3: faithful, private source landing. It does not define business KPIs,
clean away anomalies, create dbt models, or expose records to the browser. See the
[warehouse setup](warehouse-development.md), [contract](decisions/0003-warehouse-contract.md),
and [Free-plan budget](decisions/0004-development-storage-budget.md).

## Run and verify

After committed migrations and verified restricted-login provisioning:

```powershell
uv run --locked --group warehouse python -m src.warehouse load
```

Use the same command for a retry or full verification of the existing snapshot. It
reads `.env.warehouse.loader` exclusively and refuses an administrator identity. Source
preparation verifies the immutable local files before opening the database connection.
No new dependencies or PostgreSQL server installation are needed.

The source fingerprint is stable across acquisition timestamps. A retry of identical
source files re-reads and verifies the stored snapshot, preserves the original registry
and attribution, and reports `verified_existing`. Different content requires an explicit
capacity/retention review; it is never appended automatically or substituted for existing data.

Progress appears on stderr as table names only. The final stdout JSON contains only
load identity, row total, result and storage measurements. `loaded` is printed only after
commit completes. Progress saying `Copied` or `Verified` does not mean a commit happened.
Driver failures expose only their class and SQLSTATE, never connection or source detail.

## Why the load is atomic

The loader serializes warehouse operations with the existing advisory lock, inserts
one provenance record, and streams all nine tables through client COPY in one transaction.
Fields remain original text: empty strings, leading zeroes, quoted multiline reviews,
Unicode and duplicate source observations are preserved. Logical CSV ordinals and the
load UUID identify rows without imposing incorrect business uniqueness assumptions.

Before commit it independently re-reads every field in source order with bounded cursor
batches, checks full framed content digests and counts, reconciles exact PostgreSQL numeric
sums against decimal source totals, and verifies the original local files/manifest again.
Both successful loads and retries check actual storage. Raw tables plus indexes must
remain within 367,000,000 bytes and the database within 400,000,000 bytes. Initial models
remain views; this is not permission to materialize without another capacity review.

## Failure and interruption recovery

1. Preserve the CLI result, Git checkpoint and WORK_STATE. Do not print credentials or
   copy row-level errors into reports. Never manually insert a registry row to bypass checks.
2. Reconnect through the verified configuration. If commit acknowledgement was lost,
   repeat `load`: an already committed identical snapshot is fully verified, not duplicated.
3. A normal exception rolls back all nine loads and registry changes. After an abrupt
   process/connection loss, allow server cleanup before retry; a lock timeout is a reason
   to inspect the active job rather than start competing writers.
4. A changed local source or content mismatch must be investigated. Do not overwrite raw
   files or accept altered checksums just to make the load pass. Preserve the original evidence.
5. **Empty rows do not guarantee reclaimed physical storage.** A large failed COPY can
   leave allocated space even after its records become invisible. The conservative
   preflight reserves the raw ceiling again; it can refuse a retry on an empty but large
   database. Stop and measure database/table/index space; do not disable the gate.
6. For that verified-empty case, an administrator must separately review maintenance
   while no load is active: confirm all nine tables and ops.source_loads are empty and
   no other snapshot/user data is at risk. Standard VACUUM makes dead space reusable
   and may return empty trailing pages; it does not guarantee complete file shrinkage.
   If insufficient, review a targeted empty-landing TRUNCATE or isolated reconstruction
   with explicit authorization and a known-good Git/schema checkpoint. Never automate
   TRUNCATE/CASCADE, role escalation, or administrator fallback inside the loader.
7. Recheck migration checksums, all counts, privileges and actual capacity after approved
   maintenance, then retry with the restricted login. Record maintenance and measurements
   in WORK_STATE. Populated or irreplaceable state requires its own backup/restore plan.

PostgreSQL documents failed-COPY storage and vacuum behavior in its
[COPY reference](https://www.postgresql.org/docs/17/sql-copy.html) and
[vacuuming guide](https://www.postgresql.org/docs/17/routine-vacuuming.html).

## Tests and limits

Offline tests cover content corruption, malformed/missing/extra stored rows, independent
money checks, stale provenance, empty-but-allocated capacity refusal, and CLI behavior
after uncertain connection/commit outcomes. Actual LOGIN access has its own test in the
warehouse guide.

The following live recovery suite requires an **empty reviewed development landing**:

```powershell
$env:COMMERCE_WAREHOUSE_LOADING_INTEGRATION = '1'
try {
    uv run --locked --group warehouse pytest tests/test_warehouse_loading_integration.py
} finally {
    Remove-Item Env:\COMMERCE_WAREHOUSE_LOADING_INTEGRATION
}
```

Every synthetic fixture uses an outer forced rollback, including the administrator-refusal
regression test. The suite checks text/duplicate/decimal fidelity, original attribution,
idempotent retries, interrupted and changed-source rollback, capacity failures, second
snapshot refusal and administrator rejection. Do not delete real data to rerun it on a
populated target; use a replacement isolated development target. After real loading, the
`load` command verifies the committed snapshot without changing rows.

Small fixture rollback proves transaction behavior; it does not simulate every network
failure, operating-system crash, physical-size recovery, or populated backup/restore.
Full warehouse reconstruction and dbt verification remain M4/M5 acceptance work.

## Pre-load validation — 2026-09-22

151 offline tests passed; 13 live cases skipped by default. All 10 loading recovery
cases passed separately in 320.24 seconds using the actual restricted login (except
the deliberately rejected administrator case); fixtures were rolled back. Full local
style/type/build/package/advisory gates passed. Full source upload is the next acceptance
step; this pre-load checkpoint does not claim a populated warehouse.
