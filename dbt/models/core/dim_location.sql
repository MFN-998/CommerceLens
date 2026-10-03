-- One literal ZIP prefix across all three sources, including uncovered addresses.
-- Aggregate observations before joining; never select a canonical city/coordinate.
with zip_domain as (
    select customer_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_customers') }}
    union
    select seller_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_sellers') }}
    union
    select geolocation_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_geolocation') }}
), geography as (
    select
        geolocation_zip_code_prefix collate "C" as zip_code_prefix,
        count(*) as geolocation_observation_count,
        count(distinct geolocation_city collate "C") as geolocation_city_variant_count,
        count(distinct geolocation_state collate "C") as geolocation_state_variant_count,
        count(*) filter (where is_outside_broad_brazil_bounds)
            as outside_broad_brazil_observation_count
    from {{ ref('stg_geolocation') }}
    group by geolocation_zip_code_prefix collate "C"
), retained as (
    select
        z.zip_code_prefix,
        coalesce(g.geolocation_observation_count, 0) as geolocation_observation_count,
        coalesce(g.geolocation_city_variant_count, 0) as geolocation_city_variant_count,
        coalesce(g.geolocation_state_variant_count, 0) as geolocation_state_variant_count,
        coalesce(g.outside_broad_brazil_observation_count, 0)
            as outside_broad_brazil_observation_count
    from zip_domain z
    left join geography g on z.zip_code_prefix = g.zip_code_prefix
)
select
    zip_code_prefix,
    geolocation_observation_count,
    geolocation_city_variant_count,
    geolocation_state_variant_count,
    outside_broad_brazil_observation_count,
    geolocation_observation_count > 0 as has_geolocation,
    geolocation_city_variant_count > 1 as is_geolocation_city_ambiguous,
    geolocation_state_variant_count > 1 as is_geolocation_state_ambiguous
from retained
