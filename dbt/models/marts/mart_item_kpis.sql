-- Policy v1 at the retained (order_id, order_item_id) grain, without child joins.
-- Project exact source money unchanged; order outcomes belong to mart_order_kpis.
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
