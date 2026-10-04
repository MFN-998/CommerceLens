{{ config(severity='error', store_failures=false) }}
-- Required source mapping, identity and ZIP parents; all recorded calendar dates.
-- Uncovered geolocation is valid; absent optional timestamps contribute no date.
with order_facts as materialized (
    select customer_id, customer_unique_id, customer_zip_code_prefix,
        purchase_calendar_date, approval_calendar_date, carrier_delivery_calendar_date, customer_delivery_calendar_date, estimated_delivery_calendar_date
    from {{ ref('fact_orders') }}
), observed_dates as (
    select purchase_calendar_date as calendar_date from order_facts
    union all
    select approval_calendar_date as calendar_date from order_facts
    union all
    select carrier_delivery_calendar_date as calendar_date from order_facts
    union all
    select customer_delivery_calendar_date as calendar_date from order_facts
    union all
    select estimated_delivery_calendar_date as calendar_date from order_facts
), required_dates as (
    select distinct calendar_date from observed_dates where calendar_date is not null
), diagnostics as (
    select (
        select count(*) from order_facts f where not exists (
            select 1 from {{ ref('int_order_customers') }} c
            where f.customer_id collate "C" = c.customer_id collate "C"
        )
    ) as missing_customer_mapping_count, (
        select count(*) from order_facts f where not exists (
            select 1 from {{ ref('dim_customer') }} c
            where f.customer_unique_id collate "C" = c.customer_unique_id collate "C"
        )
    ) as missing_identity_count, (
        select count(*) from order_facts f where not exists (
            select 1 from {{ ref('dim_location') }} l
            where f.customer_zip_code_prefix collate "C" = l.zip_code_prefix collate "C"
        )
    ) as missing_location_count, (
        select count(*) from required_dates f where not exists (
            select 1 from {{ ref('dim_date') }} d where f.calendar_date = d.calendar_date
        )
    ) as missing_calendar_date_count
)
select * from diagnostics
where missing_customer_mapping_count > 0 or missing_identity_count > 0
    or missing_location_count > 0 or missing_calendar_date_count > 0
