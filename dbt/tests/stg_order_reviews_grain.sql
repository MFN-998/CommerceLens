{{ config(severity='error', store_failures=false) }}

-- Neither review_id nor order_id alone is the review/order pair key.
with duplicate_reviews as (
    select review_id, order_id
    from {{ ref('stg_order_reviews') }}
    group by review_id, order_id
    having count(*) > 1
)

select count(*) as duplicate_review_key_groups
from duplicate_reviews
having count(*) > 0
