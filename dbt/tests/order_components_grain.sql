{{ config(severity='error', store_failures=false) }}
select count(*) as duplicate_order_keys
from (
    select order_id collate "C" from {{ ref('mart_order_components') }}
    group by order_id collate "C" having count(*) > 1
) duplicate_keys
having count(*) > 0
