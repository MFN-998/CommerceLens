{{ config(severity='error', store_failures=false) }}

-- Compare complete row multisets in both directions. EXCEPT ALL also catches
-- duplicate rows, lost lineage and count-preserving field/identity changes.
-- This expected projection specifies the documented raw-empty-to-null rule.
with expected as (
    select
        _load_id,
        _source_row,
        nullif(customer_id, '') as customer_id,
        nullif(customer_unique_id, '') as customer_unique_id,
        nullif(customer_zip_code_prefix, '') as customer_zip_code_prefix,
        nullif(customer_city, '') as customer_city,
        nullif(customer_state, '') as customer_state
    from {{ source('raw', 'customers') }}
),
actual as (
    select
        _load_id,
        _source_row,
        customer_id,
        customer_unique_id,
        customer_zip_code_prefix,
        customer_city,
        customer_state
    from {{ ref('stg_customers') }}
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
