{{ config(severity='error', store_failures=false) }}
-- Check keys, source ordinals and NULL-safe timestamp/date correspondence.
select count(*) as invalid_order_fact_rows
from {{ ref('fact_orders') }}
where order_id is null or order_id collate "C" !~ '^[0-9a-f]{32}$'
    or customer_id is null or customer_id collate "C" !~ '^[0-9a-f]{32}$'
    or customer_unique_id is null or customer_unique_id collate "C" !~ '^[0-9a-f]{32}$'
    or customer_zip_code_prefix is null or customer_zip_code_prefix collate "C" !~ '^[0-9]{1,5}$'
    or _source_row is null or _source_row < 1
    or customer_source_row is null or customer_source_row < 1
    or purchase_calendar_date is distinct from cast(order_purchase_timestamp as date)
    or approval_calendar_date is distinct from cast(order_approved_at as date)
    or carrier_delivery_calendar_date is distinct from cast(order_delivered_carrier_date as date)
    or customer_delivery_calendar_date is distinct from cast(order_delivered_customer_date as date)
    or estimated_delivery_calendar_date is distinct from cast(order_estimated_delivery_date as date)
having count(*) > 0
