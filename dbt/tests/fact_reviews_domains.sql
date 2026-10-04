{{ config(severity='error', store_failures=false) }}
-- Literal comments and source event reversals are retained, not errors.
select count(*) as invalid_review_fact_rows
from {{ ref('fact_reviews') }}
where _load_id is null or _source_row is null or _source_row < 1
    or review_id is null or review_id !~ '^[0-9a-f]{32}$'
    or order_id is null or order_id !~ '^[0-9a-f]{32}$'
    or review_score is null or review_score not between 1 and 5
    or review_creation_date is null or review_answer_timestamp is null
    or is_answer_before_creation is distinct from
        coalesce(review_answer_timestamp < review_creation_date, false)
    or review_creation_calendar_date is distinct from cast(review_creation_date as date)
    or review_answer_calendar_date is distinct from cast(review_answer_timestamp as date)
having count(*) > 0
