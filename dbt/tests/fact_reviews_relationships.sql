{{ config(severity='error', store_failures=false) }}
-- Required membership, without joining attributes or multiplying reviews.
with reviews as materialized (
    select order_id, review_creation_calendar_date, review_answer_calendar_date
    from {{ ref('fact_reviews') }}
), required_dates as (
    select review_creation_calendar_date as calendar_date from reviews
    where review_creation_calendar_date is not null
    union
    select review_answer_calendar_date from reviews
    where review_answer_calendar_date is not null
), diagnostics as (
    select (select count(*) from reviews r where not exists (
        select 1 from {{ ref('fact_orders') }} o
        where r.order_id collate "C" = o.order_id collate "C"
    )) as missing_order_count,
    (select count(*) from required_dates r where not exists (
        select 1 from {{ ref('dim_date') }} d where r.calendar_date = d.calendar_date
    )) as missing_review_date_count
)
select * from diagnostics
where missing_order_count > 0 or missing_review_date_count > 0
