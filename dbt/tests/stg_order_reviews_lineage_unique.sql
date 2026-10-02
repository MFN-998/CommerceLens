{{ config(severity='error', store_failures=false) }}

-- Source ordinals are unique within each load, not across all source loads.
with duplicate_lineage as (
    select _load_id, _source_row
    from {{ ref('stg_order_reviews') }}
    group by _load_id, _source_row
    having count(*) > 1
)

select count(*) as duplicate_lineage_groups
from duplicate_lineage
having count(*) > 0
