{{ config(severity='error', store_failures=false) }}
-- Coverage gaps are retained warnings, not missing dimension rows. Compare
-- source-row counts, not distinct ZIP counts, and never join every geo observation.
with address_rows as (
    select 'customers' as source_name, customer_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_customers') }}
    union all
    select 'sellers' as source_name, seller_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_sellers') }}
), geography_zip_domain as (
    select distinct geolocation_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_geolocation') }}
), source_counts as (
    select a.source_name, count(*) as source_row_count,
        count(*) filter (where g.zip_code_prefix is null) as uncovered_source_row_count
    from address_rows a
    left join geography_zip_domain g on a.zip_code_prefix = g.zip_code_prefix
    group by a.source_name
), joined_counts as (
    select a.source_name, count(*) as joined_row_count,
        count(*) filter (where d.zip_code_prefix is null) as missing_dimension_row_count,
        count(*) filter (where not d.has_geolocation) as uncovered_joined_row_count
    from address_rows a
    left join {{ ref('dim_location') }} d on a.zip_code_prefix = d.zip_code_prefix collate "C"
    group by a.source_name
)
select count(*) as invalid_join_group_count
from source_counts s join joined_counts j on s.source_name = j.source_name
where s.source_row_count <> j.joined_row_count
    or j.missing_dimension_row_count > 0
    or s.uncovered_source_row_count <> j.uncovered_joined_row_count
having count(*) > 0
