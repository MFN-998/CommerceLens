{{ config(severity='error', store_failures=false) }}
-- Full literal multiset conserves optional text, events, warning and lineage.
with projected as (
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
), expected as (
    select
        _load_id,
        _source_row,
        review_id collate "C" as review_id,
        order_id collate "C" as order_id,
        review_score,
        review_comment_title collate "C" as review_comment_title,
        review_comment_message collate "C" as review_comment_message,
        review_creation_date,
        review_answer_timestamp,
        is_answer_before_creation,
        review_creation_calendar_date,
        review_answer_calendar_date
    from projected
), actual as (
    select
        _load_id,
        _source_row,
        review_id collate "C" as review_id,
        order_id collate "C" as order_id,
        review_score,
        review_comment_title collate "C" as review_comment_title,
        review_comment_message collate "C" as review_comment_message,
        review_creation_date,
        review_answer_timestamp,
        is_answer_before_creation,
        review_creation_calendar_date,
        review_answer_calendar_date
    from {{ ref('fact_reviews') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), diagnostics as (
    select (select count(*) from expected) as source_review_count,
        (select count(*) from actual) as fact_review_count,
        (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from diagnostics
where source_review_count <> fact_review_count
    or missing_or_changed_count > 0 or extra_or_changed_count > 0
