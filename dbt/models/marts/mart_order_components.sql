-- One order. Aggregate each independent child before any join; never multiply money.
-- Counts/presence are zero/false for absent children; source amount sums remain NULL.
with items as (
    select order_id collate "C" as order_id,
        count(*) as item_count,
        sum(price) as source_price_sum,
        sum(freight_value) as source_freight_sum,
        count(*) filter (where is_shipping_before_purchase) as shipping_before_purchase_count,
        count(*) filter (where is_shipping_beyond_365_days) as shipping_beyond_365_days_count
    from {{ ref('fact_order_items') }}
    group by order_id collate "C"
), payments as (
    select order_id collate "C" as order_id,
        count(*) as payment_count,
        sum(payment_value) as source_payment_sum,
        count(*) filter (where is_zero_installments) as zero_installments_count,
        count(*) filter (where is_zero_payment_value) as zero_payment_value_count,
        count(*) filter (where is_undefined_payment_type) as undefined_payment_type_count
    from {{ ref('fact_payments') }}
    group by order_id collate "C"
), reviews as (
    select order_id collate "C" as order_id,
        count(*) as review_count,
        count(*) filter (where is_answer_before_creation) as answer_before_creation_count
    from {{ ref('fact_reviews') }}
    group by order_id collate "C"
)
select
    o._load_id,
    o._source_row,
    o.order_id,
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.is_missing_approval,
    o.is_missing_carrier_delivery,
    o.is_missing_customer_delivery,
    o.is_delivered_missing_approval,
    o.is_delivered_missing_carrier_delivery,
    o.is_delivered_missing_customer_delivery,
    o.is_approval_before_purchase,
    o.is_carrier_delivery_before_purchase,
    o.is_customer_delivery_before_purchase,
    o.is_carrier_delivery_before_approval,
    o.is_customer_delivery_before_approval,
    o.is_customer_delivery_before_carrier_delivery,
    o.customer_unique_id,
    o.customer_zip_code_prefix,
    o.customer_city,
    o.customer_state,
    o.customer_load_id,
    o.customer_source_row,
    o.purchase_calendar_date,
    o.approval_calendar_date,
    o.carrier_delivery_calendar_date,
    o.customer_delivery_calendar_date,
    o.estimated_delivery_calendar_date,
    coalesce(i.item_count, 0) as item_count,
    i.source_price_sum,
    i.source_freight_sum,
    coalesce(i.shipping_before_purchase_count, 0) as shipping_before_purchase_count,
    coalesce(i.shipping_beyond_365_days_count, 0) as shipping_beyond_365_days_count,
    coalesce(i.item_count > 0, false) as has_items,
    coalesce(p.payment_count, 0) as payment_count,
    p.source_payment_sum,
    coalesce(p.zero_installments_count, 0) as zero_installments_count,
    coalesce(p.zero_payment_value_count, 0) as zero_payment_value_count,
    coalesce(p.undefined_payment_type_count, 0) as undefined_payment_type_count,
    coalesce(p.payment_count > 0, false) as has_payments,
    coalesce(r.review_count, 0) as review_count,
    coalesce(r.answer_before_creation_count, 0) as answer_before_creation_count,
    coalesce(r.review_count > 0, false) as has_reviews,
    coalesce(r.review_count > 1, false) as has_multiple_reviews
from {{ ref('fact_orders') }} o
left join items i on o.order_id collate "C" = i.order_id collate "C"
left join payments p on o.order_id collate "C" = p.order_id collate "C"
left join reviews r on o.order_id collate "C" = r.order_id collate "C"
