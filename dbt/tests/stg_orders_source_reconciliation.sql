{{ config(severity='error', store_failures=false) }}

-- Compare the complete multiset, including source attributes, lineage and flags.
-- A count-preserving edit or duplicate must fail without exposing source records.
with expected_typed as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        nullif(customer_id, '') as customer_id,
        nullif(order_status, '') as order_status,
        {{ commercelens_nullable_timestamp("nullif(order_purchase_timestamp, '')") }} as order_purchase_timestamp,
        {{ commercelens_nullable_timestamp("nullif(order_approved_at, '')") }} as order_approved_at,
        {{ commercelens_nullable_timestamp("nullif(order_delivered_carrier_date, '')") }} as order_delivered_carrier_date,
        {{ commercelens_nullable_timestamp("nullif(order_delivered_customer_date, '')") }} as order_delivered_customer_date,
        {{ commercelens_nullable_timestamp("nullif(order_estimated_delivery_date, '')") }} as order_estimated_delivery_date,
        nullif(order_approved_at, '') is null as is_missing_approval,
        nullif(order_delivered_carrier_date, '') is null as is_missing_carrier_delivery,
        nullif(order_delivered_customer_date, '') is null as is_missing_customer_delivery
    from {{ source('raw', 'orders') }}
),
expected as (
    select
        *,
        coalesce(order_status = 'delivered' and order_approved_at is null, false) as is_delivered_missing_approval,
        coalesce(order_status = 'delivered' and order_delivered_carrier_date is null, false) as is_delivered_missing_carrier_delivery,
        coalesce(order_status = 'delivered' and order_delivered_customer_date is null, false) as is_delivered_missing_customer_delivery,
        coalesce(order_approved_at < order_purchase_timestamp, false) as is_approval_before_purchase,
        coalesce(order_delivered_carrier_date < order_purchase_timestamp, false) as is_carrier_delivery_before_purchase,
        coalesce(order_delivered_customer_date < order_purchase_timestamp, false) as is_customer_delivery_before_purchase,
        coalesce(order_delivered_carrier_date < order_approved_at, false) as is_carrier_delivery_before_approval,
        coalesce(order_delivered_customer_date < order_approved_at, false) as is_customer_delivery_before_approval,
        coalesce(order_delivered_customer_date < order_delivered_carrier_date, false) as is_customer_delivery_before_carrier_delivery
    from expected_typed
),
actual as (
    select
        _load_id,
        _source_row,
        order_id,
        customer_id,
        order_status,
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
        is_customer_delivery_before_carrier_delivery
    from {{ ref('stg_orders') }}
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
