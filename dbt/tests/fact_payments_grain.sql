{{ config(severity='error', store_failures=false) }}
-- Sequence is unique within an order, never globally.
select count(*) as duplicate_payment_key_count
from (
    select order_id collate "C", payment_sequential
    from {{ ref('fact_payments') }}
    group by order_id collate "C", payment_sequential
    having count(*) > 1
) duplicate_keys
having count(*) > 0
