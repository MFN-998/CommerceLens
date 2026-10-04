{{ config(severity='error', store_failures=false) }}
-- Independently compare source-order cardinality, then the complete expected multiset.
-- The count guard detects shared expected/actual fanout from a duplicated mapping.
with source_projection as (
select
    o._load_id,
    o._source_row,
    o.order_id,
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.is_missing_approval,
    o.is_missing_carrier_delivery,
    o.is_missing_customer_delivery,
    o.is_delivered_missing_approval,
    o.is_delivered_missing_carrier_delivery,
    o.is_delivered_missing_customer_delivery,
    o.is_approval_before_purchase,
    o.is_carrier_delivery_before_purchase,
    o.is_customer_delivery_before_purchase,
    o.is_carrier_delivery_before_approval,
    o.is_customer_delivery_before_approval,
    o.is_customer_delivery_before_carrier_delivery,
    c.customer_unique_id,
    c.customer_zip_code_prefix,
    c.customer_city,
    c.customer_state,
    c._load_id as customer_load_id,
    c._source_row as customer_source_row,
    cast(o.order_purchase_timestamp as date) as purchase_calendar_date,
    cast(o.order_approved_at as date) as approval_calendar_date,
    cast(o.order_delivered_carrier_date as date) as carrier_delivery_calendar_date,
    cast(o.order_delivered_customer_date as date) as customer_delivery_calendar_date,
    cast(o.order_estimated_delivery_date as date) as estimated_delivery_calendar_date
from {{ ref('stg_orders') }} o
left join {{ ref('int_order_customers') }} c
    on o.customer_id collate "C" = c.customer_id collate "C"
), expected as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        customer_id collate "C" as customer_id,
        order_status collate "C" as order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        is_missing_approval,
        is_missing_carrier_delivery,
        is_missing_customer_delivery,
        is_delivered_missing_approval,
        is_delivered_missing_carrier_delivery,
        is_delivered_missing_customer_delivery,
        is_approval_before_purchase,
        is_carrier_delivery_before_purchase,
        is_customer_delivery_before_purchase,
        is_carrier_delivery_before_approval,
        is_customer_delivery_before_approval,
        is_customer_delivery_before_carrier_delivery,
        customer_unique_id collate "C" as customer_unique_id,
        customer_zip_code_prefix collate "C" as customer_zip_code_prefix,
        customer_city collate "C" as customer_city,
        customer_state collate "C" as customer_state,
        customer_load_id,
        customer_source_row,
        purchase_calendar_date,
        approval_calendar_date,
        carrier_delivery_calendar_date,
        customer_delivery_calendar_date,
        estimated_delivery_calendar_date
    from source_projection
), actual as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        customer_id collate "C" as customer_id,
        order_status collate "C" as order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        is_missing_approval,
        is_missing_carrier_delivery,
        is_missing_customer_delivery,
        is_delivered_missing_approval,
        is_delivered_missing_carrier_delivery,
        is_delivered_missing_customer_delivery,
        is_approval_before_purchase,
        is_carrier_delivery_before_purchase,
        is_customer_delivery_before_purchase,
        is_carrier_delivery_before_approval,
        is_customer_delivery_before_approval,
        is_customer_delivery_before_carrier_delivery,
        customer_unique_id collate "C" as customer_unique_id,
        customer_zip_code_prefix collate "C" as customer_zip_code_prefix,
        customer_city collate "C" as customer_city,
        customer_state collate "C" as customer_state,
        customer_load_id,
        customer_source_row,
        purchase_calendar_date,
        approval_calendar_date,
        carrier_delivery_calendar_date,
        customer_delivery_calendar_date,
        estimated_delivery_calendar_date
    from {{ ref('fact_orders') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), diagnostics as (
    select (select count(*) from {{ ref('stg_orders') }}) as source_order_count,
        (select count(*) from actual) as fact_order_count,
        (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from diagnostics
where source_order_count <> fact_order_count
    or missing_or_changed_count > 0 or extra_or_changed_count > 0
