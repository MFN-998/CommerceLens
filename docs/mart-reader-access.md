# Private mart reader access

Phase 3 M5. Status: SOURCE VERIFIED; live/repeat verification pending.
Continues clean mart-computation acceptance a74bd09. No model/data reload is needed.

## Scope and decision

Grant commercelens_reader SELECT only on marts.mart_order_components. Foundation
migration 0001 already grants marts USAGE. Reader remains NOLOGIN and has no elevated
capabilities or upstream memberships. No reader password/account is created before
an actual consumer needs one. Raw, staging, core and ops access, warehouse writes,
grant option, MAINTAIN and schema creation remain denied; API/PUBLIC access stays denied.

warehouse/access/mart_order_components.sql is a versioned post-model capability step,
separate from schema migrations which must run before models exist. The transformer
owns the view, so this narrowly scoped operation uses its existing dedicated login.
Guards reject unexpected session/target/role/owner/view-security options and excess
table/column privileges rather than silently removing or broadening permissions.
There are no wildcard/default grants or user-supplied targets/SQL. Reapplication is
idempotent. This is a grant on the approved private data product, not an API endpoint.

PostgreSQL views normally check underlying tables using view-owner privileges.
The reader therefore does not need source-schema access; setting security_invoker
would change that behavior and is rejected for this contract. This is not a general
claim that views are automatically secure or a row-level/multitenant boundary.
See [view access rules](https://www.postgresql.org/docs/17/sql-createview.html) and
[privilege inquiry functions](https://www.postgresql.org/docs/17/functions-info.html).

## Apply and verify

After the approved mart exists, use the dedicated transformer settings privately:

```powershell
.venv/Scripts/python.exe -B -m src.warehouse grant-mart-reader
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:COMMERCE_WAREHOUSE_MART_READER_INTEGRATION='1'
.venv/Scripts/python.exe -B -m pytest tests/test_warehouse_mart_reader_integration.py -o 'addopts=-q' --capture=sys -p no:cacheprovider --tb=short
```

The native verification uses the existing private admin configuration only to assume
the NOLOGIN reader role. It asserts the effective role, allowed aggregate/zero-row
reads, denied source reads and no table or column write privileges or grant options. No rows,
objects, memberships or credentials are created/deleted. EXPLAIN without ANALYZE
tests raw write authorization without executing it; only SQLSTATE 42501 proves denial.
This capability proof does not establish authentication or session restrictions for
a future reader login. Provision and verify that login when the later API consumer exists.

The command reports success only after the SQL transaction and connection exit cleanly.
On interruption/connection failure, verify actual privileges before retrying: a commit
may already have happened. Do not log driver detail, credentials or source records.
SQL failure before commit rolls back the ACL change. Git checkout alone does not undo database grants;
a reviewed exact REVOKE SELECT on this one mart is the inverse if rollback is required,
without deleting the view, role, source data or any project resource.

## Reconstruction sequence

1. Verify isolated target/configuration/API exposure and capacity.
2. Apply versioned schema migrations 0001/0002, provision required existing job roles,
   and load/verify the immutable source snapshot using the documented loader.
3. Build accepted staging/dimensions/mapping/facts and the order mart in dependency order.
4. Apply grant-mart-reader, verify positive and negative effective permissions, and
   confirm a compatible mart rebuild retains the grant.
5. Complete source/model/query reconciliation before accepting reconstruction.

The complete populated reconstruction proof is still pending M5; this sequence is
guidance, not a claim of a successful restore. Existing [loading](warehouse-loading.md),
[mart](order-components.md), [Phase 3 plan](phase-3-plan.md) and WORK_STATE apply.
Full governance audit follows verified Phase 3 before Phase 4, not this scoped review.
