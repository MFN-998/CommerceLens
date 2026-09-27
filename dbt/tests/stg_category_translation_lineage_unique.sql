{{ config(severity='error', store_failures=false) }}

-- The ordinal is unique within a load, not globally across future source loads.
with duplicate_lineage as (
    select _load_id, _source_row
    from {{ ref('stg_category_translation') }}
    group by _load_id, _source_row
    having count(*) > 1
)

select count(*) as duplicate_lineage_groups
from duplicate_lineage
having count(*) > 0
