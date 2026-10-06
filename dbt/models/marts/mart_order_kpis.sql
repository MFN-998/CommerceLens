-- Policy v1, one order; preserve the technical mart and every warning/lineage field.
-- Extra child aggregates expose missing amounts and equal-order review weighting.
with item_coverage as (
    select order_id collate "C" as order_id,
        count(price) as priced_items,
        count(freight_value) as freight_items
    from {{ ref('fact_order_items') }}
    group by order_id collate "C"
), payment_coverage as (
    select order_id collate "C" as order_id, count(payment_value) as valued_payments
    from {{ ref('fact_payments') }}
    group by order_id collate "C"
), review_metrics as (
    select order_id collate "C" as order_id,
        count(review_score) as scored_reviews,
        sum(review_score) as review_score_sum,
        count(*) filter (where review_score between 1 and 2) as low_review_count,
        count(*) filter (where review_score between 4 and 5) as high_review_count,
        sum(review_score)::numeric / nullif(count(review_score), 0) as order_review_score,
        count(*) filter (where review_score between 1 and 2)::numeric
            / nullif(count(review_score), 0) as order_low_review_fraction,
        count(*) filter (where review_score between 4 and 5)::numeric
            / nullif(count(review_score), 0) as order_high_review_fraction
    from {{ ref('fact_reviews') }}
    group by order_id collate "C"
), policy as (
    select c.*,
        'v1'::text as policy_version,
        coalesce(c.order_status collate "C" = 'delivered', false) as is_commerce_eligible,
        coalesce(i.priced_items, 0) as priced_items,
        coalesce(i.freight_items, 0) as freight_items,
        coalesce(p.valued_payments, 0) as valued_payments,
        c.item_count > 0 and i.priced_items = c.item_count as is_price_complete,
        c.item_count > 0 and i.freight_items = c.item_count as is_freight_complete,
        c.payment_count > 0 and p.valued_payments = c.payment_count as is_payment_complete,
        coalesce(r.scored_reviews, 0) as scored_reviews,
        r.order_review_score,
        r.order_low_review_fraction,
        r.order_high_review_fraction,
        coalesce(r.review_score_sum, 0) as review_score_sum,
        coalesce(r.low_review_count, 0) as low_review_count,
        coalesce(r.high_review_count, 0) as high_review_count,
        coalesce(c.order_status collate "C" = 'delivered'
            and c.order_purchase_timestamp is not null
            and c.order_delivered_customer_date is not null
            and c.order_delivered_customer_date >= c.order_purchase_timestamp,
            false) as is_delivery_eligible
    from {{ ref('mart_order_components') }} c
    left join item_coverage i on c.order_id collate "C" = i.order_id collate "C"
    left join payment_coverage p on c.order_id collate "C" = p.order_id collate "C"
    left join review_metrics r on c.order_id collate "C" = r.order_id collate "C"
), promise as (
    select policy.*,
        coalesce(is_delivery_eligible and order_estimated_delivery_date is not null
            and order_estimated_delivery_date >= order_purchase_timestamp,
            false) as is_promise_eligible
    from policy
)
select promise.*,
    case when is_delivery_eligible then
        extract(epoch from (order_delivered_customer_date - order_purchase_timestamp))
        end as delivery_seconds,
    case when is_promise_eligible then
        customer_delivery_calendar_date > estimated_delivery_calendar_date
        end as is_calendar_late,
    case when is_promise_eligible then
        order_delivered_customer_date > order_estimated_delivery_date
        end as is_timestamp_late,
    case when is_promise_eligible then
        extract(epoch from (order_delivered_customer_date - order_estimated_delivery_date))
        end as promise_difference_seconds
from promise
