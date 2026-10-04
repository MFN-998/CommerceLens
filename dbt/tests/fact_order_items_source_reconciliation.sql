{{ config(severity='error', store_failures=false) }}
-- Independent source-item count blocks shared expected/actual parent fanout.
-- Compare every source/context/flag/date field as a complete multiset.
with source_projection as (
select
    i._load_id,
    i._source_row,
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    i.shipping_limit_date,
    i.price,
    i.freight_value,
    o.order_purchase_timestamp,
    o._load_id as order_load_id,
    o._source_row as order_source_row,
    coalesce(i.shipping_limit_date < o.order_purchase_timestamp, false) as is_shipping_before_purchase,
    coalesce(i.shipping_limit_date - o.order_purchase_timestamp > interval '365 days', false) as is_shipping_beyond_365_days,
    cast(i.shipping_limit_date as date) as shipping_calendar_date
from {{ ref('stg_order_items') }} i
left join {{ ref('fact_orders') }} o
    on i.order_id collate "C" = o.order_id collate "C"
), expected as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        order_item_id,
        product_id collate "C" as product_id,
        seller_id collate "C" as seller_id,
        shipping_limit_date,
        price,
        freight_value,
        order_purchase_timestamp,
        order_load_id,
        order_source_row,
        is_shipping_before_purchase,
        is_shipping_beyond_365_days,
        shipping_calendar_date
    from source_projection
), actual as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        order_item_id,
        product_id collate "C" as product_id,
        seller_id collate "C" as seller_id,
        shipping_limit_date,
        price,
        freight_value,
        order_purchase_timestamp,
        order_load_id,
        order_source_row,
        is_shipping_before_purchase,
        is_shipping_beyond_365_days,
        shipping_calendar_date
    from {{ ref('fact_order_items') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), diagnostics as (
    select (select count(*) from {{ ref('stg_order_items') }}) as source_item_count,
        (select count(*) from actual) as fact_item_count,
        (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from diagnostics
where source_item_count <> fact_item_count
    or missing_or_changed_count > 0 or extra_or_changed_count > 0
