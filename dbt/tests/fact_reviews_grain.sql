{{ config(severity='error', store_failures=false) }}
-- Neither identifier is globally unique; preserve every literal pair.
select count(*) as duplicate_review_key_count
from (
    select review_id collate "C", order_id collate "C"
    from {{ ref('fact_reviews') }}
    group by review_id collate "C", order_id collate "C"
    having count(*) > 1
) duplicate_keys
having count(*) > 0
