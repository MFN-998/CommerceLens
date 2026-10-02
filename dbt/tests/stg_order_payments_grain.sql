{{ config(severity='error', store_failures=false) }}

-- Component sequence is unique within its order, not across different orders.
with duplicate_payments as (
    select order_id, payment_sequential
    from {{ ref('stg_order_payments') }}
    group by order_id, payment_sequential
    having count(*) > 1
)

select count(*) as duplicate_payment_key_groups
from duplicate_payments
having count(*) > 0
