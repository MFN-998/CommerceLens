{{ config(severity='error', store_failures=false) }}
-- Required core references; no parent attribute joins or output filtering.
with item_facts as materialized (
    select order_id, product_id, seller_id, shipping_calendar_date
    from {{ ref('fact_order_items') }}
), required_dates as (
    select distinct shipping_calendar_date from item_facts
    where shipping_calendar_date is not null
), diagnostics as (
    select (
        select count(*) from item_facts f where not exists (
            select 1 from {{ ref('fact_orders') }} o
            where f.order_id collate "C" = o.order_id collate "C"
        )
    ) as missing_order_count, (
        select count(*) from item_facts f where not exists (
            select 1 from {{ ref('dim_product') }} p
            where f.product_id collate "C" = p.product_id collate "C"
        )
    ) as missing_product_count, (
        select count(*) from item_facts f where not exists (
            select 1 from {{ ref('dim_seller') }} s
            where f.seller_id collate "C" = s.seller_id collate "C"
        )
    ) as missing_seller_count, (
        select count(*) from required_dates f where not exists (
            select 1 from {{ ref('dim_date') }} d
            where f.shipping_calendar_date = d.calendar_date
        )
    ) as missing_shipping_date_count
)
select * from diagnostics
where missing_order_count > 0 or missing_product_count > 0
    or missing_seller_count > 0 or missing_shipping_date_count > 0
