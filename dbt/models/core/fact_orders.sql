-- One retained source order, with unchanged lifecycle/quality/lineage.
-- Only the order-linked customer mapping joins here; independent children stay separate.
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
    c.customer_unique_id,
    c.customer_zip_code_prefix,
    c.customer_city,
    c.customer_state,
    c._load_id as customer_load_id,
    c._source_row as customer_source_row,
    cast(o.order_purchase_timestamp as date) as purchase_calendar_date,
    cast(o.order_approved_at as date) as approval_calendar_date,
    cast(o.order_delivered_carrier_date as date) as carrier_delivery_calendar_date,
    cast(o.order_delivered_customer_date as date) as customer_delivery_calendar_date,
    cast(o.order_estimated_delivery_date as date) as estimated_delivery_calendar_date
from {{ ref('stg_orders') }} o
left join {{ ref('int_order_customers') }} c
    on o.customer_id collate "C" = c.customer_id collate "C"
