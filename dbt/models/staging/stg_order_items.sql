-- Retain all seven literal source fields and lineage at (order_id, order_item_id).
-- No parent purchase join: shipping-before-purchase and beyond-365-day contextual
-- flags belong to fact_order_items later, together with any duration eligibility.
-- Exact empty text becomes NULL; rejected numeric/date text becomes typed NULL
-- and fails blocking tests. Price/freight zero is valid and retained without flags.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        nullif(order_item_id, '') as order_item_id,
        nullif(product_id, '') as product_id,
        nullif(seller_id, '') as seller_id,
        nullif(shipping_limit_date, '') as shipping_limit_date,
        nullif(price, '') as price,
        nullif(freight_value, '') as freight_value
    from {{ source('raw', 'order_items') }}
)

select
    _load_id,
    _source_row,
    order_id,
    {{ commercelens_nullable_bigint('order_item_id') }} as order_item_id,
    product_id,
    seller_id,
    {{ commercelens_nullable_timestamp('shipping_limit_date') }} as shipping_limit_date,
    {{ commercelens_nullable_money('price') }} as price,
    {{ commercelens_nullable_money('freight_value') }} as freight_value
from normalized
