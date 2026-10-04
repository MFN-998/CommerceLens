-- One retained order-linked source customer_id with purchase-associated address.
-- Repeated cross-order identities keep every address and original source lineage.
select
    _load_id,
    _source_row,
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
from {{ ref('stg_customers') }}
