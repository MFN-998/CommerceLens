{{ config(severity='error', store_failures=false) }}

-- Compare complete row multisets in both directions. EXCEPT ALL also catches
-- duplicate rows, lost lineage and count-preserving field/identity changes.
-- This expected projection specifies the documented raw-empty-to-null rule.
with expected as (
    select
        _load_id,
        _source_row,
        nullif(seller_id, '') as seller_id,
        nullif(seller_zip_code_prefix, '') as seller_zip_code_prefix,
        nullif(seller_city, '') as seller_city,
        nullif(seller_state, '') as seller_state
    from {{ source('raw', 'sellers') }}
),
actual as (
    select
        _load_id,
        _source_row,
        seller_id,
        seller_zip_code_prefix,
        seller_city,
        seller_state
    from {{ ref('stg_sellers') }}
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
