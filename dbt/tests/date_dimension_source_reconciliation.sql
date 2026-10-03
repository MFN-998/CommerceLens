{{ config(severity='error', store_failures=false) }}
-- Independently derive observed source date membership and its standard calendar
-- attributes. Full bidirectional multisets detect omissions, extras and fanout.
with source_events as (
    select order_purchase_timestamp as event_timestamp from {{ ref('stg_orders') }}
    union all
    select order_approved_at from {{ ref('stg_orders') }}
    union all
    select order_delivered_carrier_date from {{ ref('stg_orders') }}
    union all
    select order_delivered_customer_date from {{ ref('stg_orders') }}
    union all
    select order_estimated_delivery_date from {{ ref('stg_orders') }}
    union all
    select shipping_limit_date from {{ ref('stg_order_items') }}
    union all
    select review_creation_date from {{ ref('stg_order_reviews') }}
    union all
    select review_answer_timestamp from {{ ref('stg_order_reviews') }}
), source_dates as (
    select distinct cast(event_timestamp as date) as calendar_date
    from source_events
    where event_timestamp is not null
), expected as (
    select
        calendar_date,
        cast(extract(year from calendar_date) as integer) as calendar_year,
        cast(extract(quarter from calendar_date) as integer) as calendar_quarter,
        cast(extract(month from calendar_date) as integer) as calendar_month,
        cast(extract(day from calendar_date) as integer) as day_of_month,
        cast(extract(isoyear from calendar_date) as integer) as iso_year,
        cast(extract(week from calendar_date) as integer) as iso_week,
        cast(extract(isodow from calendar_date) as integer) as iso_day_of_week,
        extract(isodow from calendar_date) in (6, 7) as is_weekend
    from source_dates
), actual as (
    select calendar_date, calendar_year, calendar_quarter, calendar_month,
        day_of_month, iso_year, iso_week, iso_day_of_week, is_weekend
    from {{ ref('dim_date') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), differences as (
    select (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from differences
where missing_or_changed_count > 0 or extra_or_changed_count > 0
