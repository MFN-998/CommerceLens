{{ config(severity='error', store_failures=false) }}
-- Conserve the complete parent multiset, including literal text, events and lineage.
with expected as materialized (
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
), actual as materialized (
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
    from {{ ref('mart_order_components') }}
), missing_or_changed as (
    select * from expected except all select * from actual
), extra_or_changed as (
    select * from actual except all select * from expected
)
select (select count(*) from missing_or_changed) as missing_or_changed_count,
    (select count(*) from extra_or_changed) as extra_or_changed_count
where (select count(*) from expected) <> (select count(*) from actual)
    or exists (select 1 from missing_or_changed) or exists (select 1 from extra_or_changed)
