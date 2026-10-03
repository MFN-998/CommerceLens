{{ config(severity='error', store_failures=false) }}
-- Invalid identities remain visible rather than being filtered or repaired.
select count(*) as invalid_customer_dimension_rows
from {{ ref('dim_customer') }}
where customer_unique_id is null
    or customer_unique_id collate "C" !~ '^[0-9a-f]{32}$'
having count(*) > 0
