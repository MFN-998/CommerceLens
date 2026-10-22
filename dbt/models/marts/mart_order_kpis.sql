-- Policy v1, one order; preserve the technical mart and every warning/lineage field.
-- Coverage and review inputs share the existing independent child aggregates.
with components as (
    {{ order_components(include_kpi_inputs=true) }}
), policy as (
    select
        c._load_id,
        c._source_row,
        c.order_id,
        c.customer_id,
        c.order_status,
        c.order_purchase_timestamp,
        c.order_approved_at,
        c.order_delivered_carrier_date,
        c.order_delivered_customer_date,
        c.order_estimated_delivery_date,
        c.is_missing_approval,
        c.is_missing_carrier_delivery,
        c.is_missing_customer_delivery,
        c.is_delivered_missing_approval,
        c.is_delivered_missing_carrier_delivery,
        c.is_delivered_missing_customer_delivery,
        c.is_approval_before_purchase,
        c.is_carrier_delivery_before_purchase,
        c.is_customer_delivery_before_purchase,
        c.is_carrier_delivery_before_approval,
        c.is_customer_delivery_before_approval,
        c.is_customer_delivery_before_carrier_delivery,
        c.customer_unique_id,
        c.customer_zip_code_prefix,
        c.customer_city,
        c.customer_state,
        c.customer_load_id,
        c.customer_source_row,
        c.purchase_calendar_date,
        c.approval_calendar_date,
        c.carrier_delivery_calendar_date,
        c.customer_delivery_calendar_date,
        c.estimated_delivery_calendar_date,
        c.item_count,
        c.source_price_sum,
        c.source_freight_sum,
        c.shipping_before_purchase_count,
        c.shipping_beyond_365_days_count,
        c.has_items,
        c.payment_count,
        c.source_payment_sum,
        c.zero_installments_count,
        c.zero_payment_value_count,
        c.undefined_payment_type_count,
        c.has_payments,
        c.review_count,
        c.answer_before_creation_count,
        c.has_reviews,
        c.has_multiple_reviews,
        'v1'::text as policy_version,
        coalesce(c.order_status collate "C" = 'delivered', false) as is_commerce_eligible,
        coalesce(c.priced_items, 0) as priced_items,
        coalesce(c.freight_items, 0) as freight_items,
        coalesce(c.valued_payments, 0) as valued_payments,
        c.item_count > 0 and c.priced_items = c.item_count as is_price_complete,
        c.item_count > 0 and c.freight_items = c.item_count as is_freight_complete,
        c.payment_count > 0 and c.valued_payments = c.payment_count as is_payment_complete,
        coalesce(c.scored_reviews, 0) as scored_reviews,
        c.review_score_sum::numeric / nullif(c.scored_reviews, 0) as order_review_score,
        c.low_review_count::numeric / nullif(c.scored_reviews, 0) as order_low_review_fraction,
        c.high_review_count::numeric / nullif(c.scored_reviews, 0) as order_high_review_fraction,
        coalesce(c.review_score_sum, 0) as review_score_sum,
        coalesce(c.low_review_count, 0) as low_review_count,
        coalesce(c.high_review_count, 0) as high_review_count,
        coalesce(c.order_status collate "C" = 'delivered'
            and c.order_purchase_timestamp is not null
            and c.order_delivered_customer_date is not null
            and c.order_delivered_customer_date >= c.order_purchase_timestamp,
            false) as is_delivery_eligible
    from components c
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
