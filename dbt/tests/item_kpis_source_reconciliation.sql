{{ config(severity='error', store_failures=false) }}
-- Keep the independently derived order fact as the status/presence oracle.
-- Compare all 26 fields as literal multisets and reject shared parent fanout.
with source_projection as (
select
    i.*,
    'v1'::text as policy_version,
    o.order_status,
    coalesce(o.order_status collate "C" = 'delivered', false) as is_commerce_eligible,
    o.order_id is null as is_missing_order,
    p.product_id is null as is_missing_product,
    p._load_id as product_load_id,
    p._source_row as product_source_row,
    p.product_category_name,
    p.product_category_name_english,
    p.is_missing_category,
    p.is_untranslated_category
from {{ ref('fact_order_items') }} i
left join {{ ref('fact_orders') }} o
    on i.order_id collate "C" = o.order_id collate "C"
left join {{ ref('dim_product') }} p
    on i.product_id collate "C" = p.product_id collate "C"
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
        shipping_calendar_date,
        policy_version collate "C" as policy_version,
        order_status collate "C" as order_status,
        is_commerce_eligible,
        is_missing_order,
        is_missing_product,
        product_load_id,
        product_source_row,
        product_category_name collate "C" as product_category_name,
        product_category_name_english collate "C" as product_category_name_english,
        is_missing_category,
        is_untranslated_category
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
        shipping_calendar_date,
        policy_version collate "C" as policy_version,
        order_status collate "C" as order_status,
        is_commerce_eligible,
        is_missing_order,
        is_missing_product,
        product_load_id,
        product_source_row,
        product_category_name collate "C" as product_category_name,
        product_category_name_english collate "C" as product_category_name_english,
        is_missing_category,
        is_untranslated_category
    from {{ ref('mart_item_kpis') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), diagnostics as (
    select (select count(*) from {{ ref('fact_order_items') }}) as source_item_count,
        (select count(*) from actual) as mart_item_count,
        (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from diagnostics
where source_item_count <> mart_item_count
    or missing_or_changed_count > 0 or extra_or_changed_count > 0
