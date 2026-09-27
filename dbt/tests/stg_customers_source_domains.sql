{{ config(severity='error', store_failures=false) }}

-- Source format rules, not source repairs. Return only an aggregate diagnostic.
select count(*) as invalid_source_value_rows
from {{ ref('stg_customers') }}
where customer_id is null
    or customer_id !~ '^[0-9a-f]{32}$'
    or customer_unique_id is null
    or customer_unique_id !~ '^[0-9a-f]{32}$'
    or customer_zip_code_prefix is null
    or customer_zip_code_prefix !~ '^[0-9]{1,5}$'
    or _source_row is null
    or _source_row < 1
having count(*) > 0
