{% macro item_order_projection(include_parent=false) %}
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
    {% if include_parent %}, o.order_id as _parent_order_id, o.order_status as _parent_order_status{% endif %}
from {{ ref('stg_order_items') }} i
left join {{ ref('stg_orders') }} o
    on i.order_id collate "C" = o.order_id collate "C"
{% endmacro %}
