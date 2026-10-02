{{ config(severity='error', store_failures=false) }}

-- Full multiset comparison covers all source fields, lineage and the reversal
-- flag. Count-preserving text/date changes or duplicate substitutions must fail.
-- Return only aggregate mismatch counts, never review text or identifiers.
with expected_typed as (
    select
        _load_id,
        _source_row,
        nullif(review_id, '') as review_id,
        nullif(order_id, '') as order_id,
        {{ commercelens_nullable_bigint("nullif(review_score, '')") }} as review_score,
        nullif(review_comment_title, '') as review_comment_title,
        nullif(review_comment_message, '') as review_comment_message,
        {{ commercelens_nullable_timestamp("nullif(review_creation_date, '')") }} as review_creation_date,
        {{ commercelens_nullable_timestamp("nullif(review_answer_timestamp, '')") }} as review_answer_timestamp
    from {{ source('raw', 'order_reviews') }}
),
expected as (
    select
        *,
        coalesce(review_answer_timestamp < review_creation_date, false) as is_answer_before_creation
    from expected_typed
),
actual as (
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
        is_answer_before_creation
    from {{ ref('stg_order_reviews') }}
),
missing_from_staging as (
    select * from expected
    except all
    select * from actual
),
unexpected_in_staging as (
    select * from actual
    except all
    select * from expected
)

select 'missing_from_staging' as mismatch, count(*) as row_count
from missing_from_staging
having count(*) > 0
union all
select 'unexpected_in_staging' as mismatch, count(*) as row_count
from unexpected_in_staging
having count(*) > 0
