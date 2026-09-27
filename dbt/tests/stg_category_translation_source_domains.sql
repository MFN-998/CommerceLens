{{ config(severity='error', store_failures=false) }}

-- Retain invalid ordinals for diagnosis and return only an aggregate count.
select count(*) as invalid_source_value_rows
from {{ ref('stg_category_translation') }}
where _source_row is null
    or _source_row < 1
having count(*) > 0
