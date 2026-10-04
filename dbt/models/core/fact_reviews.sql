-- Every source review/order pair; neither ID alone is unique.
-- Preserve literal optional text, lineage, score, events and reversal warning.
-- Direct calendar roles, no join/filter/aggregation or selected-review policy.
select
    _load_id,
    _source_row,
    review_id,
    order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    review_creation_date,
    review_answer_timestamp,
    is_answer_before_creation,
    cast(review_creation_date as date) as review_creation_calendar_date,
    cast(review_answer_timestamp as date) as review_answer_calendar_date
from {{ ref('stg_order_reviews') }}
