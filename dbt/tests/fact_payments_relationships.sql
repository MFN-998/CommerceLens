{{ config(severity='error', store_failures=false) }}
-- Membership avoids parent fanout and retains every component.
select count(*) as missing_order_count
from {{ ref('fact_payments') }} p
where not exists (
    select 1 from {{ ref('fact_orders') }} o
    where p.order_id collate "C" = o.order_id collate "C"
)
having count(*) > 0
