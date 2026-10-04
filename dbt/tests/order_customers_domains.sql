{{ config(severity='error', store_failures=false) }}
-- Validate source key/ZIP/ordinal domains without trimming or repairing records.
-- Required city absence and state membership are tested by the configured generics.
select count(*) as invalid_order_customer_rows
from {{ ref('int_order_customers') }}
where customer_id is null or customer_id collate "C" !~ '^[0-9a-f]{32}$'
    or customer_unique_id is null or customer_unique_id collate "C" !~ '^[0-9a-f]{32}$'
    or customer_zip_code_prefix is null
    or customer_zip_code_prefix collate "C" !~ '^[0-9]{1,5}$'
    or _source_row is null or _source_row < 1
having count(*) > 0
