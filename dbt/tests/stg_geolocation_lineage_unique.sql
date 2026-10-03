{{ config(severity='error', store_failures=false) }}

-- ZIPs and identical source observations may repeat. Only lineage is unique.
with duplicate_lineage as (
    select _load_id, _source_row
    from {{ ref('stg_geolocation') }}
    group by _load_id, _source_row
    having count(*) > 1
)

select count(*) as duplicate_lineage_groups
from duplicate_lineage
having count(*) > 0
