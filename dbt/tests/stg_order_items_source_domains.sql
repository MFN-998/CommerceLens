{{ config(severity='error', store_failures=false) }}

-- All source attributes are mandatory. Invalid/missing typed values block
-- acceptance while retaining rows. Return aggregate diagnostics only.
select count(*) as invalid_source_value_rows
from {{ ref('stg_order_items') }}
where _load_id is null
    or _source_row is null
    or _source_row < 1
    or order_id is null
    or order_id !~ '^[0-9a-f]{32}$'
    or order_item_id is null
    or order_item_id < 1
    or product_id is null
    or product_id !~ '^[0-9a-f]{32}$'
    or seller_id is null
    or seller_id !~ '^[0-9a-f]{32}$'
    or shipping_limit_date is null
    or price is null
    or price < 0
    or price > 9999999999999999.99
    or freight_value is null
    or freight_value < 0
    or freight_value > 9999999999999999.99
having count(*) > 0
