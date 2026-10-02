{{ config(severity='error', store_failures=false) }}

-- An item sequence is unique within its order, not across different orders.
with duplicate_items as (
    select order_id, order_item_id
    from {{ ref('stg_order_items') }}
    group by order_id, order_item_id
    having count(*) > 1
)

select count(*) as duplicate_item_key_groups
from duplicate_items
having count(*) > 0
