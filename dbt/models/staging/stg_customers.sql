-- One row per source customer_id; customer_unique_id may repeat across orders.
-- Only literal empty source strings become null. Do not trim, pad, change case,
-- choose an address, deduplicate identities, or join geography at this boundary.
select
    _load_id,
    _source_row,
    nullif(customer_id, '') as customer_id,
    nullif(customer_unique_id, '') as customer_unique_id,
    nullif(customer_zip_code_prefix, '') as customer_zip_code_prefix,
    nullif(customer_city, '') as customer_city,
    nullif(customer_state, '') as customer_state
from {{ source('raw', 'customers') }}
