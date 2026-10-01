{{ config(severity='error', store_failures=false) }}

-- Mandatory values and rejected nonempty dates fail; optional source absence is
-- valid. Lifecycle reversals and delivered-missing warnings do not discard rows.
-- Return aggregate diagnostics only, without source identifiers or date text.
select count(*) as invalid_source_value_rows
from {{ ref('stg_orders') }} as staged
left join {{ source('raw', 'orders') }} as original
    on staged._load_id = original._load_id
    and staged._source_row = original._source_row
where staged.order_id is null
    or staged.order_id !~ '^[0-9a-f]{32}$'
    or staged.customer_id is null
    or staged.customer_id !~ '^[0-9a-f]{32}$'
    or staged.order_status is null
    or staged.order_status not in ('created', 'approved', 'invoiced', 'processing', 'shipped', 'delivered', 'unavailable', 'canceled')
    or staged._source_row is null
    or staged._source_row < 1
    or staged.order_purchase_timestamp is null
    or staged.order_estimated_delivery_date is null
    or (nullif(original.order_purchase_timestamp, '') is not null and staged.order_purchase_timestamp is null)
    or (nullif(original.order_approved_at, '') is not null and staged.order_approved_at is null)
    or (nullif(original.order_delivered_carrier_date, '') is not null and staged.order_delivered_carrier_date is null)
    or (nullif(original.order_delivered_customer_date, '') is not null and staged.order_delivered_customer_date is null)
    or (nullif(original.order_estimated_delivery_date, '') is not null and staged.order_estimated_delivery_date is null)
having count(*) > 0
