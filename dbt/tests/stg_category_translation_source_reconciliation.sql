{{ config(severity='error', store_failures=false) }}

-- Compare full row multisets, including lineage, in both directions. This
-- catches lost or duplicate rows and count-preserving category/translation edits.
with expected as (
    select
        _load_id,
        _source_row,
        nullif(product_category_name, '') as product_category_name,
        nullif(product_category_name_english, '') as product_category_name_english
    from {{ source('raw', 'category_translation') }}
),
actual as (
    select
        _load_id,
        _source_row,
        product_category_name,
        product_category_name_english
    from {{ ref('stg_category_translation') }}
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
