{{ config(severity='error', store_failures=false) }}
-- Independently derive coverage from the unique observation ZIP domain, not
-- from dim_location's coverage value. Compare every source field and lineage;
-- bidirectional multisets also detect join fanout or discarded uncovered rows.
with geography_zip_domain as (
    select distinct geolocation_zip_code_prefix collate "C" as zip_code_prefix
    from {{ ref('stg_geolocation') }}
), expected as (
    select
        s._load_id, s._source_row, s.seller_id, s.seller_zip_code_prefix,
        s.seller_city, s.seller_state,
        g.zip_code_prefix is not null as has_geolocation
    from {{ ref('stg_sellers') }} s
    left join geography_zip_domain g
        on s.seller_zip_code_prefix collate "C" = g.zip_code_prefix
), actual as (
    select _load_id, _source_row, seller_id, seller_zip_code_prefix,
        seller_city, seller_state, has_geolocation
    from {{ ref('dim_seller') }}
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
