# ADR 0003: Phase 3 warehouse contract and development isolation

Status: Accepted design for M1, 2026-09-20. **Not yet implemented or database-tested.**
Authority: master-plan Phase 3 and the owner's dedicated Supabase development selection.
Inputs: [source dictionary](../data_dictionary/initial.md), [quality report](../data-quality-report.md),
[source observations](../warehouse-source-observations.json), and [ADR 0002](0002-source-quality.md).

## Why this boundary matters

Phase 2 produced faithful, typed local data with documented warnings. PostgreSQL/dbt must
now make analytical relationships safe without changing the source history. The database
design therefore separates source preservation, standardization, reusable entities/facts,
and purposeful marts. A dashboard/API is not required to establish this foundation.

## Schemas and types

| Schema | Responsibility | Ownership/access intent |
| --- | --- | --- |
| `ops` | Migration/load registry and provenance/check evidence | Migration owner; loader only the registry operations it needs |
| `raw` | Nine landed CSV tables, source text, manifest/load identity, logical source-row ordinal | Owned by migration role; loader inserts new verified loads; no routine UPDATE/DELETE |
| `staging` | dbt source standardization with explicit types, names, and quality flags | Transformer creates/rebuilds models; raw remains unchanged |
| `core` | Tested dimensions and facts at declared grains | Transformer owns models |
| `marts` | Small analytical datasets at explicit consumer grains | Transformer writes; restricted reader may select approved marts |

Schemas stay private to database clients, outside the Data API exposed-schema list.
Do not place warehouse tables in `public` merely because it is the default schema.
Verify anonymous/authenticated API roles have no warehouse privileges. RLS is assessed
for any future API exposure; it does not replace correct schema/table privileges.

| Source category | Warehouse representation | Reason / validation |
| --- | --- | --- |
| Source IDs and ZIP prefixes | `text`, preserving source spelling/leading zeroes | Validate ID format and existing ZIP contract; no UUID reformatting or numeric ZIP conversion |
| Nullable source integers | `bigint` plus domain checks | Preserve Phase 2 signed-64-bit contract; positive sequence and score/domain checks remain explicit |
| Price, freight, payment amount | `numeric(18,2)` | Original CSV Decimal values; reject excess scale or range before PostgreSQL could round; no Float64-to-money conversion |
| Source event timestamps | `timestamp without time zone` | Source declares no timezone and has second-resolution text; do not invent UTC conversion |
| Geography coordinates | `double precision` plus validation/quality flags | Appropriate numerical representation for coordinates; original text remains in raw |
| Categories, city names, review text | `text`, nullability explicit in staging | Preserve source meaning; raw empty strings become staging nulls only by the documented rule |

The numeric choice leaves headroom beyond observed values without introducing an accounting
policy. All inspected money fields have scale ≤ 2; maxima are 6,735.00 price, 409.68 freight,
and 13,664.08 payment value. Source-column sums in the observations are **technical load
reconciliation values**, not GMV/revenue definitions. Do not force item+freight sums to
equal payment sums without a separately justified business reconciliation rule.

Raw database landing is parsed source text with lineage, not a replacement for immutable
CSV bytes. Keep source-file hashes/version/manifest and `_source_row` (logical CSV record,
not physical line). A complete load is identified through a registry; reruns verify the
existing matching load instead of blindly appending rows. Test the exact registry key and
content checks when implementing M3. Empty source strings must not silently become raw NULL.

## Table grains and safe relationships

| Intended model | Declared grain/key | Join and retention decision |
| --- | --- | --- |
| `dim_customer` | One `customer_unique_id` | Cross-order identity only; do not choose a current address from arbitrary source rows |
| `int_order_customers` | One source `customer_id` | Preserve order-linked identity and purchase-associated city/state/ZIP for fact_orders |
| `dim_product` | One `product_id` | Left join the unique category translation; distinguish missing category from missing translation |
| `dim_seller` | One `seller_id` | Preserve source address and ZIP relationship; mark missing geolocation coverage |
| `dim_location` | One literal ZIP prefix in the union of customer/seller/geolocation sources | Retain observation counts, coverage and city/state ambiguity; no invented canonical coordinate/city |
| `dim_date` | One calendar date across retained event dates | Standard calendar attributes only; timestamps remain available and invalid-event eligibility is separate |
| `fact_orders` | One `order_id` | All source orders; link customer identity through order_customer; preserve source status/location/lifecycle |
| `fact_order_items` | `(order_id, order_item_id)` | All item rows; relationships to order/product/seller |
| `fact_payments` | `(order_id, payment_sequential)` | All payment components, including flagged zero/undefined values |
| `fact_reviews` | `(review_id, order_id)` | All review/order pairs; neither ID alone is a unique review key |
| `mart_order_components` | One `order_id` | Independently aggregate each child first, then left join to orders; expose counts/amount components and quality flags |

No separate delivery fact is necessary initially: order-level delivery events and flags
live in fact_orders. Add a one-row-per-order delivery projection only when a real query
needs it. Do not create duplicate fact definitions just to fill a diagram.

The technical order mart includes counts, source price/freight/payment sums, review count,
and source event/quality indicators. Do not choose a canonical review or assert business
eligibility at this stage. Any selected-review rule, customer-current-location policy,
representative ZIP coordinate, or delivered-only KPI denominator requires a future explicit decision.

## Treatment of every Phase 2 warning family

- **Geography:** preserve all 1,000,163 observations in raw/staging, including 261,831 excess
  exact duplicates and 31 broad-Brazil-box outliers. The unique ZIP dimension reports coverage
  and ambiguity; it does not join every observation to each order or silently discard points.
- **Missing ZIP coverage:** include customer/seller ZIPs in the dimension union; flag the
  278/7 source rows without geolocation evidence. Unknown geography is not a reason to drop an order.
- **Multiple reviews:** preserve all pairs and expose counts; 547 orders have multiple reviews.
- **Event reversals/missing lifecycle timestamps:** retain source dates/status; add named validity
  and missingness flags. Only expose a duration when its required events are present and ordered.
- **Orders lacking items/payments/reviews:** left joins preserve all orders; child count zero and
  presence flags distinguish absence from a measured monetary zero. Amount sums remain null
  when no component exists unless a consumer explicitly chooses a later zero-fill policy.
- **Missing product attributes/category/translation and zero weight:** retain null/zero values
  and separate flags; distinguish the 610 missing categories from 13 untranslated product rows.
- **Zero installments/value and undefined payment type:** preserve and flag; no invented replacement.
- **Shipping deadlines beyond one year:** preserve and flag the exploratory threshold; do not
  rewrite it as a business deadline rule. Future source versions rerun all these diagnostics.

Mandatory missing references and confirmed-key violations still fail validation. Optional
coverage warnings do not weaken row-retention or join-conservation tests.

## Access, loading, migrations, and recovery contract

Use distinct capability roles, with credentials outside Git: migration/owner, loader,
transformer, and mart reader. Roles may be NOLOGIN groups with only the necessary login
memberships added for actual tools; do not invent four credentials before their use exists.
Loader has no blanket schema ownership or transformation rights; transformer reads raw
and rebuilds its own schemas; reader has no raw access or writes. The browser gets no
database credentials. Verify both allowed operations and expected permission denials.

M2 must capture actual project/region/PostgreSQL version and encrypted connection method.
Use direct connections for native migration/backup tools where reachable; inspect the
actual session-pooler alternative when local IPv6 access is unavailable. Never disable
certificate checks as a connectivity workaround or infer the pooler host from a region.
No hosted resources or paid options are authorized by this design alone.

Bootstrap SQL/migrations are versioned, reviewed, and tracked in the database. Use a
dedicated development target, pre-risk Git checkpoint, and a disposable validation target
for retry/rollback tests. M3 loads a full source snapshot transactionally so a failure
cannot publish a partial ready load. Test idempotency and content/count/decimal reconciliation.
Use COPY/batched insertion, bounded connections, keys and evidence-driven indexes.

Initially, immutable source plus versioned migrations/dbt can rebuild disposable analytical
state. Prove that reconstruction before accepting the warehouse. Before any irreplaceable
or shared state, establish protected backups, retention, restore testing, and clear recovery
ownership; Git is not a database backup. Do not depend on an unverified Supabase plan's backup features.

## Acceptance and references

M1 accepts the contract only. M2–M5 must verify it through actual SQL/dbt/load/recovery tests;
no database success is claimed here. See [Phase 3 plan](../phase-3-plan.md) and WORK_STATE
for the precise current checkpoint and next action.

- [PostgreSQL numeric types](https://www.postgresql.org/docs/current/datatype-numeric.html).
- [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres).
- [Supabase API security](https://supabase.com/docs/guides/api/securing-your-api).
- [dbt Postgres setup](https://docs.getdbt.com/docs/local/connect-data-platform/postgres-setup).
