{{ config(severity='error', store_failures=false) }}

-- Complete multiset comparison includes all five source fields, immutable
-- lineage and the warning flag. EXCEPT ALL catches duplicate loss/substitution
-- and count-preserving coordinate/text edits; return aggregate diagnostics only.
with expected_typed as (
    select
        _load_id,
        _source_row,
        nullif(geolocation_zip_code_prefix, '') as geolocation_zip_code_prefix,
        {{ commercelens_nullable_double("nullif(geolocation_lat, '')") }} as geolocation_lat,
        {{ commercelens_nullable_double("nullif(geolocation_lng, '')") }} as geolocation_lng,
        nullif(geolocation_city, '') as geolocation_city,
        nullif(geolocation_state, '') as geolocation_state
    from {{ source('raw', 'geolocation') }}
),
expected as (
    select
        *,
        coalesce(
            geolocation_lat is not null
            and geolocation_lng is not null
            and (
                geolocation_lat not between -34 and 6
                or geolocation_lng not between -74 and -28
            ),
            false
        ) as is_outside_broad_brazil_bounds
    from expected_typed
),
actual as (
    select
        _load_id,
        _source_row,
        geolocation_zip_code_prefix,
        geolocation_lat,
        geolocation_lng,
        geolocation_city,
        geolocation_state,
        is_outside_broad_brazil_bounds
    from {{ ref('stg_geolocation') }}
),
missing_from_staging as (
    select * from expected
    except all
    select * from actual
),
unexpected_in_staging as (
    select * from actual
    except all
    select * from expected
)

select 'missing_from_staging' as mismatch, count(*) as row_count
from missing_from_staging
having count(*) > 0
union all
select 'unexpected_in_staging' as mismatch, count(*) as row_count
from unexpected_in_staging
having count(*) > 0
