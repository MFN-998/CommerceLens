# Phase 5 isolated native verification

## Current checkpoint — 2026-10-16

Both first native builds passed: order10 selected tests and item12 selected tests.
The existing mart identities/permissions and raw size were preserved. Do not
repeat the build commands below merely to resume. Next is independent native KPI
acceptance, then the explicit reader grant/catalog/denial gate. See
[build evidence](phase-5-native-build-verification.json) and WORK_STATE.md.

The restored recovery project's direct hostname failed DNS. Its dashboard's
IPv4 session-pooler route passed with existing credentials and verify-full TLS;
only private recovery admin/transformer routing was updated, with protected
backups retained. No original-project settings or passwords changed.

The measurement CLI now supervises all database stages under one600-second
budget, reserving2 seconds for worker cleanup. Connection/statement limits shrink
with remaining time; fixed stage markers survive interruption. Workload coverage,
parameter/model provenance and native acceptance remain pending: do not run or
accept Q01 just because deadline integration passes offline checks.

## Scoped build and recovery reference

The selected runner supports only `mart_order_kpis` and `mart_item_kpis` on an
explicit isolated test target. It parses the complete closed graph offline,
builds only the selected view, and requires all eagerly selected tests to pass.
Test-only operations run those checks without rebuilding. It never expands to
ancestors, changes credentials, reloads sources, retries, or deletes artifacts.

Use the existing recovery root and target recorded in
[reconstruction evidence](warehouse-reconstruction-verification.json). Recheck
account reserve and the latest WORK_STATE before any native invocation. The
original project and ambient WAREHOUSE/PG routing variables are rejected.

From the repository root, the intended first native step is:

```powershell
.venv/Scripts/python.exe -B -m scripts.phase5_native build-order --settings-root 'D:\My Projects\CommerceLens-Reconstruction' --expected-project-ref histbcmlctxmtxusfbzt
```

Inspect its retained receipt and catalog/capacity evidence before proceeding to
`build-item` with the same explicit arguments. `test-order` and `test-item` rerun
only the selected checks. Do not invoke the historical full-graph build path for
these additions. A native operation has not passed merely because tooling tests
or the offline graph parse passed.

Subprocess stdout/stderr and file logs are disabled. Each run retains unique
preflight/live artifacts under the isolated root's `.artifacts/dbt-selected`,
and the wrapper retains before/after metadata under repository `.artifacts/phase-5`.
The runner checks the entire preflight/live graph contract, distinct invocation
identity, exact selected result set and zero test failures. SQL/lock/idle limits
remain60/10/60 seconds; setup/selected subprocess limits remain120/180 seconds,
one dbt thread and no retry. These limits are not Q01 consumer latency acceptance.

The preserving view materialization can commit before tests finish. Failure
evidence distinguishes no dispatch, an uncertain committed build after dispatch,
and a verified committed build followed by a receipt/metadata failure. Inspect
the selected relation and retained evidence before retrying. Do not drop, reset
or assume rollback; Git cannot roll back the database. Permission or disk failures
can prevent a receipt write, so retain the exception's fixed recovery facts too.

After native model checks, verify independent precision/grain/coverage, reviews,
calendar lateness and dashboard reconciliation. Extend and verify reader catalog
and denial checks before Q01. The current `verify-totals` checks only three
historical totals and does not satisfy full KPI acceptance. Q01 deadline,
representative workload/concurrency and provenance improvements remain required
before running/accepting measurements. No consumer authentication or HTTP/UI
integration is certified here; those remain Phase6.
