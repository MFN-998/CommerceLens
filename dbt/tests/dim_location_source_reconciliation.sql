{{ config(severity='error', store_failures=false) }}
-- Independent grouped multiplicities preserve duplicates rather than treating
-- city/state/flag combinations as unique source observations. No raw values returned.
with source_zip_rows as (
    select customer_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_customers') }}
    union all
    select seller_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_sellers') }}
    union all
    select geolocation_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_geolocation') }}
), zip_domain as (
    select zip_code_prefix from source_zip_rows group by zip_code_prefix
), observation_groups as (
    select
        geolocation_zip_code_prefix collate "C" as zip_code_prefix,
        geolocation_city collate "C" as city,
        geolocation_state collate "C" as state,
        is_outside_broad_brazil_bounds as outside_box,
        count(*) as multiplicity
    from {{ ref('stg_geolocation') }}
    group by geolocation_zip_code_prefix collate "C", geolocation_city collate "C",
        geolocation_state collate "C", is_outside_broad_brazil_bounds
), expected_geography as (
    select
        zip_code_prefix,
        cast(sum(multiplicity) as bigint) as observation_count,
        count(distinct city) as city_count,
        count(distinct state) as state_count,
        cast(sum(case when outside_box then multiplicity else 0 end) as bigint) as outside_count
    from observation_groups
    group by zip_code_prefix
), expected as (
    select
        z.zip_code_prefix,
        coalesce(g.observation_count, 0) as geolocation_observation_count,
        coalesce(g.city_count, 0) as geolocation_city_variant_count,
        coalesce(g.state_count, 0) as geolocation_state_variant_count,
        coalesce(g.outside_count, 0) as outside_broad_brazil_observation_count,
        coalesce(g.observation_count, 0) > 0 as has_geolocation,
        coalesce(g.city_count, 0) > 1 as is_geolocation_city_ambiguous,
        coalesce(g.state_count, 0) > 1 as is_geolocation_state_ambiguous
    from zip_domain z left join expected_geography g on z.zip_code_prefix = g.zip_code_prefix
), actual as (
    select zip_code_prefix, geolocation_observation_count, geolocation_city_variant_count,
        geolocation_state_variant_count, outside_broad_brazil_observation_count,
        has_geolocation, is_geolocation_city_ambiguous, is_geolocation_state_ambiguous
    from {{ ref('dim_location') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), differences as (
    select (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from differences
where missing_or_changed_count > 0 or extra_or_changed_count > 0
