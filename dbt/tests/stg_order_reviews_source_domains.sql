{{ config(severity='error', store_failures=false) }}

-- Optional comment absence and actual event reversal remain valid source rows.
-- Missing/rejected mandatory values block acceptance; aggregate diagnostics only.
select count(*) as invalid_source_value_rows
from {{ ref('stg_order_reviews') }}
where _load_id is null
    or _source_row is null
    or _source_row < 1
    or review_id is null
    or review_id !~ '^[0-9a-f]{32}$'
    or order_id is null
    or order_id !~ '^[0-9a-f]{32}$'
    or review_score is null
    or review_score not between 1 and 5
    or review_creation_date is null
    or review_answer_timestamp is null
having count(*) > 0
