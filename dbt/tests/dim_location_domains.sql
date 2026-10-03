{{ config(severity='error', store_failures=false) }}
-- Invalid upstream ZIPs stay visible; never filter them to pass a dimension test.
with source_zips as (
    select customer_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_customers') }}
    union all
    select seller_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_sellers') }}
    union all
    select geolocation_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_geolocation') }}
), source_failures as (
    select count(*) as invalid_source_zip_count
    from source_zips
    where zip_code_prefix is null or zip_code_prefix !~ '^[0-9]{1,5}$'
), geography_input_failures as (
    -- Aggregates ignore NULLs; reject them even among otherwise valid variants.
    select count(*) as invalid_geography_input_count
    from {{ ref('stg_geolocation') }}
    where geolocation_city is null or geolocation_state is null
        or is_outside_broad_brazil_bounds is null
), dimension_failures as (
    select count(*) as invalid_dimension_row_count
    from {{ ref('dim_location') }}
    where zip_code_prefix is null or zip_code_prefix collate "C" !~ '^[0-9]{1,5}$'
        or geolocation_observation_count < 0
        or geolocation_city_variant_count < 0
        or geolocation_state_variant_count < 0
        or outside_broad_brazil_observation_count < 0
        or geolocation_city_variant_count > geolocation_observation_count
        or geolocation_state_variant_count > geolocation_observation_count
        or outside_broad_brazil_observation_count > geolocation_observation_count
        or (geolocation_observation_count > 0 and (
            geolocation_city_variant_count = 0 or geolocation_state_variant_count = 0
        ))
        or has_geolocation is distinct from (geolocation_observation_count > 0)
        or is_geolocation_city_ambiguous is distinct from (geolocation_city_variant_count > 1)
        or is_geolocation_state_ambiguous is distinct from (geolocation_state_variant_count > 1)
)
select invalid_source_zip_count, invalid_geography_input_count, invalid_dimension_row_count
from source_failures cross join geography_input_failures cross join dimension_failures
where invalid_source_zip_count > 0 or invalid_geography_input_count > 0
    or invalid_dimension_row_count > 0
