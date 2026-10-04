# Technical order-component queries

These three aggregate-only examples read the accepted private
`marts.mart_order_components` view under effective `commercelens_reader`.
They introduce no child joins, source repair, status eligibility, selected review,
duration, business finding or official revenue/GMV definition.

| Query | Population and result |
| --- | --- |
| `order_component_totals.sql` | Every retained order; one row of 33 aggregates, including an empty input. |
| `purchase_month_components.sql` | Every status; one row per observed purchase month plus a NULL-month group if present. |
| `purchase_period_status_components.sql` | Purchases in the bound half-open period; one row per literal C-collated status, including NULL status if present. |

The grouped queries add their grouping field before the same 33 aggregate fields.
They return no rows for an empty population and generate no absent month/status groups.
Upstream validation remains required; retaining a synthetic NULL group does not
make a missing required source timestamp or status acceptable.

## Output contract

- `order_count` counts retained mart orders. `item_count`, `payment_count` and
  `review_count` sum accepted source components/pairs, including split payments
  and every review association.
- `source_price_sum`, `source_freight_sum` and `source_payment_sum` sum their
  separate unchanged source amounts. No equality between them is asserted.
- `orders_with_items/payments/reviews` and `orders_without_items/payments/reviews`
  count each family's presence/absence. `orders_with_multiple_reviews` counts
  the accepted multiple-review flag without choosing a review.
- `orders_with_measured_zero_payment_sum` requires payment presence and a recorded
  per-order payment sum of zero. It differs from `zero_payment_value_count`,
  which counts individual zero-value payment components, including those in an
  order with other positive components.
- Six child warning fields retain their existing names: shipping before purchase,
  shipping beyond 365 days, zero installments, zero payment value, undefined method,
  and answer before creation. Each sums the accepted component warning count.
- Twelve fields ending in `_order_count` count the corresponding retained
  order warning: three missing events, three delivered-but-missing events, and
  six event reversals. Warnings can overlap; their sum is not a distinct-order count.

Counts are zero for an empty totals input. Amount sums remain SQL NULL if the
population has no measured amounts from that family; measured zeros remain zero.
Only count sums use COALESCE. Native numeric sums retain exact money and aggregate
headroom; there is no numeric(18,2) recast or float conversion.

## Period binding and execution

Supply `start` and `end` as Python `datetime.date` objects in psycopg's parameter
mapping, with `start < end`. The SQL casts them to timestamp without time zone:
start is inclusive midnight and end is exclusive midnight. NULL purchase timestamps
cannot satisfy either range comparison. All qualifying statuses remain, without
case conversion or whitespace normalization.

Use a bound execution such as `connection.execute(sql, {"start": start, "end": end})`.
Dates must not be interpolated into the SQL text. Monthly grouping also uses the
unchanged timestamp without inventing a timezone or a current-date default.

Source/static/offline verification passed; SQL not yet executed. Native result verification and measured plans
under the existing reader are still pending; no performance or populated recovery
claim is made here. Keep the existing read-only transaction/timeouts and aggregate-only
output policy. The NOLOGIN capability is already verified; a future consumer login
requires its own authentication/session verification.

