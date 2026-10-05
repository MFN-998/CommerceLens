# CommerceLens KPI dictionary — policy v1

Defined for Phase 5 on 2026-10-05. Historical anonymized Olist version2, BRL;
not a live business, recognized accounting revenue, profit or settled cash.
This is the authoritative policy for forthcoming Phase 5 metric implementations.
Implementation/native/workload acceptance remains pending in phase-5-plan.md.

## Shared population and filters

Commerce eligibility is literal order_status = delivered. Other statuses remain
in the warehouse and in separately named all-status source/status diagnostics;
never silently broaden delivered commerce totals. This choice describes observed
fulfilled merchandise, with no assertion about refunds/returns or accounting.
Orders count every delivered order, independently of child presence or timestamps.
Missing/reversed lifecycle events do not exclude a commerce order: each operational
metric has its own declared valid-event denominator and coverage counts.

All dashboard periods filter order_purchase_timestamp using inclusive start midnight
and exclusive end midnight on the original naive clock. No invented timezone or UTC
suffix. Boundaries are validated calendar dates; start must precede end. Monthly/daily
trends use that same purchase cohort, not delivery/review dates. No synthetic calendar
rows or complete-marketplace-period claim; boundary months remain coverage caveats.
A future alternative event clock requires a distinct versioned metric name.

Category/seller filters use existence of an item association for order-level metrics,
never a direct many-child join. Merchandise/freight amounts and units in those slices
come only from matching items. Payment values cannot be attributed to individual
categories/sellers from this source and are unavailable for those filtered slices.
Order outcomes are associations, not attribution of seller/category responsibility.
Customer geography is the purchase-associated order state, with unknown values retained.
Category identity is the literal source category with separate missing/translation
coverage; an absent label cannot drop an item. Literal ZIP/source identity is unchanged.
No canonical address/review/geolocation point is selected.

## Missingness, exact money and empty populations

Independently aggregate items, payments and reviews before joining orders. Child
presence/counts and non-null component counts accompany monetary metrics. Missing
children and incomplete amount families are unknown, never measured zero. For a
nonempty slice, a complete total is NULL if any relevant eligible component family
is absent or contains a missing required amount. Publish the separately named known
amount sum plus measured/missing-order counts; do not label a partial sum total GMV.
Actual source zeros are included. Price and freight completeness are independent.
Empty population: counts0, additive money0.00, ratios/meansNULL. A populated slice
with no known amounts has known amount sumNULL. Coverage makes these distinguishable.

Use native numeric/Decimal or integer cents; no binary float money arithmetic.
Aggregate without imposing numeric(18,2) headroom on sums. BRL totals serialize as
fixed two-decimal strings. AOV serializes as a two-decimal string using decimal
ROUND_HALF_UP at the response boundary only. Rates/scores/durations serialize as
six-decimal strings, with the exact additive numerator/denominator also exposed;
NULL stays JSON null. Never round components before sum/division, and never average
already rounded group means. Numeric counts are integers within a validated safe
JSON integer range; reject overflow safely. All outputs carry policy_version=v1.

## Dictionary

| Metric key | Definition / numerator | Denominator / coverage |
| --- | --- | --- |
| orders | Distinct delivered order_id in the selected purchase cohort | Every eligible order, including missing children |
| gmv | Complete sum of eligible item price, excluding freight | NULL on incomplete price coverage; separate known_gmv and priced_orders |
| units | Count retained eligible item rows; one row is one source item unit | Missing-item orders reported; no inferred quantity |
| freight_value | Complete sum eligible item freight_value | Independent freight coverage; separate known_freight_value |
| payment_value | Complete sum every payment component of eligible orders | Independent payment coverage; includes zero/undefined methods; unavailable for category/seller attribution |
| aov | gmv / orders | NULL for zero orders or incomplete GMV; no item-only denominator substitution |
| active_customers | Distinct literal customer_unique_id across eligible orders | Source cross-order identity, not customer_id or selected address |
| delivery_days | Sum actual-delivery minus purchase seconds /86400 | Delivered orders with both events present and actual >= purchase |
| late_delivery_rate | Count actual calendar date > estimated calendar date | Delivery-valid orders with estimate present and estimate >= purchase; both late and on_time share this denominator |
| on_time_rate | Count actual calendar date <= estimated calendar date | Same denominator as late_delivery_rate; equality is on time |
| promise_difference_days | Sum signed actual-delivery minus estimate seconds /86400 | Same valid-promise population; negative means earlier; no clipping |
| timestamp_late_rate | Count actual timestamp > estimated timestamp | Same population; diagnostic, distinct from official calendar lateness |
| mean_review_score | Sum per-order arithmetic mean of all retained review-pair scores | Reviewed eligible orders; one equal weight per order |
| low_rating_rate | Sum per-order fraction of review-pair scores1–2 | Same reviewed-order denominator; no rounding an order mean into a rating class |
| high_rating_rate | Sum per-order fraction of review-pair scores4–5 | Same reviewed-order denominator; score3 is neutral |
| review_coverage | Count eligible orders with >=1 review pair | All eligible orders; absent reviews are excluded from rating denominators |
| seller_gmv / category_gmv | Sum item price attributed once to matching seller/category | Same completeness policy; disjoint item-value partitions reconcile platform GMV |
| seller_orders / category_orders | Distinct associated eligible orders | Associations overlap; never sum into platform order counts |
| seller_late_rate / category_late_rate | Official late/order-valid population over distinct associations | Same promise rule; expose support, no hidden >=100 cutoff or ranking significance claim |
| seller_rating / category_rating | Equal-order-weight review metric over distinct associations | Same review policy; order-level association only |
| state_orders / state_gmv | Eligible orders / item GMV grouped by purchase-associated customer state | Include unknown group; additive counts/value partitions reconcile platform |
| customer_concentration | State distinct active customers / platform active customers | Customers can occur across states; shares overlap and are not additive |

Calendar lateness treats the source midnight estimate as a promised calendar day,
not a declared midnight SLA. It differs deliberately from timestamp_late_rate.
A reversed promise clock is excluded from both comparisons, with explicit counts;
other intermediate approval/carrier warnings remain visible without changing the
required-event eligibility. Duration validity and promise validity are separate.

Reviews retain every (review_id,order_id) pair. Equal-order weighting avoids giving
multi-review orders extra influence and selects no canonical review. Also expose
review_pairs and multiple_review_orders; pair-weighted score is a separately named
diagnostic. Group partitions reconcile additive score/fraction sums and denominators,
not means. Single-review analysis and seller>=100 in Phase4 remain exploratory.

## Future-phase contracts

New/repeat customer, recency/frequency/monetary, cohorts and retention products remain
Phase7. Their eventual definitions must use the same delivered eligibility, literal
cross-order identity and explicit historical observation window; policy extension
requires versioned definitions, tests and no retroactive metric-name substitution.
Post-order delivery, reviews and final statuses are historical outcomes. They are
not eligible order-time predictive features; later historical seller features must
be calculated strictly before each prediction cutoff with chronological evaluation.

## Cross-dashboard acceptance

Executive and trend/geography outputs use one shared population/policy. Reconcile
all additive numerators, denominators, coverage and known money exactly. Category
and seller item-price/freight/unit partitions reconcile at item grain; their orders,
customers and outcomes overlap. Filtered executive order outcomes must match distinct
association oracles while matching-item values agree with item-grain oracles.
Synthetic acceptance covers empty/missing/partial/zero money, large exact sums,
multiple children/reviews, cross-state repeat identities, same-day promise equality,
reversals/missing events, literal categories and half-open/leap-day boundaries.
No public HTTP endpoint or consumer auth is accepted by this policy document.
