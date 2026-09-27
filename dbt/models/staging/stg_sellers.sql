-- One row per source seller_id. Preserve the source address and lineage.
-- Only literal empty source strings become null. Do not trim, pad, change case,
-- deduplicate sellers, or join geography at this boundary.
select
    _load_id,
    _source_row,
    nullif(seller_id, '') as seller_id,
    nullif(seller_zip_code_prefix, '') as seller_zip_code_prefix,
    nullif(seller_city, '') as seller_city,
    nullif(seller_state, '') as seller_state
from {{ source('raw', 'sellers') }}
