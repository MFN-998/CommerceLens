-- Retain every source review/order pair, all seven fields and immutable lineage.
-- Optional title/message preserve literal text; only exact empty text becomes NULL.
-- Reversed events remain unchanged and flagged. No parent join, selected review,
-- duration or KPI rule is added. Multiple-review counts belong to core/marts later.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(review_id, '') as review_id,
        nullif(order_id, '') as order_id,
        nullif(review_score, '') as review_score,
        nullif(review_comment_title, '') as review_comment_title,
        nullif(review_comment_message, '') as review_comment_message,
        nullif(review_creation_date, '') as review_creation_date,
        nullif(review_answer_timestamp, '') as review_answer_timestamp
    from {{ source('raw', 'order_reviews') }}
),
typed as (
    select
        _load_id,
        _source_row,
        review_id,
        order_id,
        {{ commercelens_nullable_bigint('review_score') }} as review_score,
        review_comment_title,
        review_comment_message,
        {{ commercelens_nullable_timestamp('review_creation_date') }} as review_creation_date,
        {{ commercelens_nullable_timestamp('review_answer_timestamp') }} as review_answer_timestamp
    from normalized
)

select
    *,
    coalesce(review_answer_timestamp < review_creation_date, false) as is_answer_before_creation
from typed
