-- Observed calendar dates across all accepted event columns, without status or
-- warning filters. NULL event absence contributes no date; parsing fails upstream.
with observed_events as (
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
), observed_dates as (
    select distinct cast(event_timestamp as date) as calendar_date
    from observed_events
    where event_timestamp is not null
)
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
from observed_dates
