{{ config(severity='error', store_failures=false) }}
-- Both fields define one source item; an order may legitimately repeat.
with duplicate_keys as (
    select order_id collate "C" as order_id, order_item_id
    from {{ ref('fact_order_items') }}
    group by order_id collate "C", order_item_id
    having count(*) > 1
)
select count(*) as duplicate_item_key_count from duplicate_keys
having count(*) > 0
