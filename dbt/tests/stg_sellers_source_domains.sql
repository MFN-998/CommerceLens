{{ config(severity='error', store_failures=false) }}

-- Source format rules, not source repairs. Return only an aggregate diagnostic.
select count(*) as invalid_source_value_rows
from {{ ref('stg_sellers') }}
where seller_id is null
    or seller_id !~ '^[0-9a-f]{32}$'
    or seller_zip_code_prefix is null
    or seller_zip_code_prefix !~ '^[0-9]{1,5}$'
    or _source_row is null
    or _source_row < 1
having count(*) > 0
