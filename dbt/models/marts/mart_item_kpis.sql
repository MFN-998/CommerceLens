-- Policy v1 at the retained (order_id, order_item_id) grain, without child joins.
-- Project exact source money unchanged; order outcomes belong to mart_order_kpis.
with item_context as (
    {{ item_order_projection(include_parent=true) }}
)
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
    i.order_purchase_timestamp,
    i.order_load_id,
    i.order_source_row,
    i.is_shipping_before_purchase,
    i.is_shipping_beyond_365_days,
    i.shipping_calendar_date,
    'v1'::text as policy_version,
    i._parent_order_status as order_status,
    coalesce(i._parent_order_status collate "C" = 'delivered', false) as is_commerce_eligible,
    i._parent_order_id is null as is_missing_order,
    p.product_id is null as is_missing_product,
    p._load_id as product_load_id,
    p._source_row as product_source_row,
    p.product_category_name,
    p.product_category_name_english,
    p.is_missing_category,
    p.is_untranslated_category
from item_context i
left join {{ ref('dim_product') }} p
    on i.product_id collate "C" = p.product_id collate "C"
