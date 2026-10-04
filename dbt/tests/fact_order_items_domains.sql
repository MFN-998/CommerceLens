{{ config(severity='error', store_failures=false) }}
-- Source domains, exact chronology flags and NULL-safe timestamp/date correspondence.
select count(*) as invalid_item_fact_rows
from {{ ref('fact_order_items') }}
where order_id is null or order_id collate "C" !~ '^[0-9a-f]{32}$'
    or product_id is null or product_id collate "C" !~ '^[0-9a-f]{32}$'
    or seller_id is null or seller_id collate "C" !~ '^[0-9a-f]{32}$'
    or order_item_id is null or order_item_id < 1
    or _source_row is null or _source_row < 1
    or order_source_row is null or order_source_row < 1
    or price is null or price < 0 or price > 9999999999999999.99
    or freight_value is null or freight_value < 0 or freight_value > 9999999999999999.99
    or shipping_calendar_date is distinct from cast(shipping_limit_date as date)
    or is_shipping_before_purchase is distinct from
        coalesce(shipping_limit_date < order_purchase_timestamp, false)
    or is_shipping_beyond_365_days is distinct from
        coalesce(shipping_limit_date - order_purchase_timestamp > interval '365 days', false)
having count(*) > 0
