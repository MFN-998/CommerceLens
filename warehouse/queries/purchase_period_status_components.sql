-- Bind Python date values as start/end with psycopg; never interpolate SQL.
-- Include start midnight and exclude end midnight, with every literal status.
select
    order_status collate "C" as order_status,
    count(*) as order_count,
    coalesce(sum(item_count), 0) as item_count,
    sum(source_price_sum) as source_price_sum,
    sum(source_freight_sum) as source_freight_sum,
    count(*) filter (where has_items) as orders_with_items,
    count(*) filter (where not has_items) as orders_without_items,
    coalesce(sum(shipping_before_purchase_count), 0) as shipping_before_purchase_count,
    coalesce(sum(shipping_beyond_365_days_count), 0) as shipping_beyond_365_days_count,
    coalesce(sum(payment_count), 0) as payment_count,
    sum(source_payment_sum) as source_payment_sum,
    count(*) filter (where has_payments) as orders_with_payments,
    count(*) filter (where not has_payments) as orders_without_payments,
    count(*) filter (where has_payments and source_payment_sum = 0)
        as orders_with_measured_zero_payment_sum,
    coalesce(sum(zero_installments_count), 0) as zero_installments_count,
    coalesce(sum(zero_payment_value_count), 0) as zero_payment_value_count,
    coalesce(sum(undefined_payment_type_count), 0) as undefined_payment_type_count,
    coalesce(sum(review_count), 0) as review_count,
    count(*) filter (where has_reviews) as orders_with_reviews,
    count(*) filter (where not has_reviews) as orders_without_reviews,
    count(*) filter (where has_multiple_reviews) as orders_with_multiple_reviews,
    coalesce(sum(answer_before_creation_count), 0) as answer_before_creation_count,
    count(*) filter (where is_missing_approval) as missing_approval_order_count,
    count(*) filter (where is_missing_carrier_delivery) as missing_carrier_delivery_order_count,
    count(*) filter (where is_missing_customer_delivery) as missing_customer_delivery_order_count,
    count(*) filter (where is_delivered_missing_approval) as delivered_missing_approval_order_count,
    count(*) filter (where is_delivered_missing_carrier_delivery)
        as delivered_missing_carrier_delivery_order_count,
    count(*) filter (where is_delivered_missing_customer_delivery)
        as delivered_missing_customer_delivery_order_count,
    count(*) filter (where is_approval_before_purchase) as approval_before_purchase_order_count,
    count(*) filter (where is_carrier_delivery_before_purchase)
        as carrier_delivery_before_purchase_order_count,
    count(*) filter (where is_customer_delivery_before_purchase)
        as customer_delivery_before_purchase_order_count,
    count(*) filter (where is_carrier_delivery_before_approval)
        as carrier_delivery_before_approval_order_count,
    count(*) filter (where is_customer_delivery_before_approval)
        as customer_delivery_before_approval_order_count,
    count(*) filter (where is_customer_delivery_before_carrier_delivery)
        as customer_delivery_before_carrier_delivery_order_count
from marts.mart_order_components
where order_purchase_timestamp >= %(start)s::timestamp
    and order_purchase_timestamp < %(end)s::timestamp
group by order_status collate "C"
order by order_status collate "C" nulls first;

