-- Retain every source order and literal status; no child joins or repaired dates.
-- Source missingness is independent of parsing. Invalid nonempty timestamp text
-- becomes typed NULL and fails the blocking source-domain test.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        nullif(customer_id, '') as customer_id,
        nullif(order_status, '') as order_status,
        nullif(order_purchase_timestamp, '') as order_purchase_timestamp,
        nullif(order_approved_at, '') as order_approved_at,
        nullif(order_delivered_carrier_date, '') as order_delivered_carrier_date,
        nullif(order_delivered_customer_date, '') as order_delivered_customer_date,
        nullif(order_estimated_delivery_date, '') as order_estimated_delivery_date
    from {{ source('raw', 'orders') }}
),
typed as (
    select
        _load_id,
        _source_row,
        order_id,
        customer_id,
        order_status,
        {{ commercelens_nullable_timestamp('order_purchase_timestamp') }} as order_purchase_timestamp,
        {{ commercelens_nullable_timestamp('order_approved_at') }} as order_approved_at,
        {{ commercelens_nullable_timestamp('order_delivered_carrier_date') }} as order_delivered_carrier_date,
        {{ commercelens_nullable_timestamp('order_delivered_customer_date') }} as order_delivered_customer_date,
        {{ commercelens_nullable_timestamp('order_estimated_delivery_date') }} as order_estimated_delivery_date,
        order_approved_at is null as is_missing_approval,
        order_delivered_carrier_date is null as is_missing_carrier_delivery,
        order_delivered_customer_date is null as is_missing_customer_delivery
    from normalized
)

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
from typed
