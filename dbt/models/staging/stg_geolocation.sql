-- Retain every source observation and immutable lineage, including exact duplicates.
-- ZIPs and source city/state spelling stay literal; no geography join, padding,
-- representative coordinate, filtering or deduplication is introduced.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(geolocation_zip_code_prefix, '') as geolocation_zip_code_prefix,
        nullif(geolocation_lat, '') as geolocation_lat,
        nullif(geolocation_lng, '') as geolocation_lng,
        nullif(geolocation_city, '') as geolocation_city,
        nullif(geolocation_state, '') as geolocation_state
    from {{ source('raw', 'geolocation') }}
),
typed as (
    select
        _load_id,
        _source_row,
        geolocation_zip_code_prefix,
        {{ commercelens_nullable_double('geolocation_lat') }} as geolocation_lat,
        {{ commercelens_nullable_double('geolocation_lng') }} as geolocation_lng,
        geolocation_city,
        geolocation_state
    from normalized
)

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
from typed
