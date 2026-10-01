{{ config(severity='error', store_failures=false) }}

-- Full multiset comparison includes every attribute, source identity and flag.
-- Detect loss, duplication and count-preserving edits; never expose source rows.
with expected as (
    select
        _load_id,
        _source_row,
        nullif(product_id, '') as product_id,
        nullif(product_category_name, '') as product_category_name,
        {{ commercelens_nullable_bigint("nullif(product_name_lenght, '')") }} as product_name_lenght,
        {{ commercelens_nullable_bigint("nullif(product_description_lenght, '')") }} as product_description_lenght,
        {{ commercelens_nullable_bigint("nullif(product_photos_qty, '')") }} as product_photos_qty,
        {{ commercelens_nullable_double("nullif(product_weight_g, '')") }} as product_weight_g,
        {{ commercelens_nullable_double("nullif(product_length_cm, '')") }} as product_length_cm,
        {{ commercelens_nullable_double("nullif(product_height_cm, '')") }} as product_height_cm,
        {{ commercelens_nullable_double("nullif(product_width_cm, '')") }} as product_width_cm,
        nullif(product_category_name, '') is null as is_missing_category,
        nullif(product_name_lenght, '') is null as is_missing_name_length,
        nullif(product_description_lenght, '') is null as is_missing_description_length,
        nullif(product_photos_qty, '') is null as is_missing_photos_qty,
        nullif(product_weight_g, '') is null as is_missing_weight,
        nullif(product_length_cm, '') is null as is_missing_length,
        nullif(product_height_cm, '') is null as is_missing_height,
        nullif(product_width_cm, '') is null as is_missing_width,
        coalesce({{ commercelens_nullable_double("nullif(product_weight_g, '')") }} = 0, false) as is_zero_weight
    from {{ source('raw', 'products') }}
),
actual as (
    select
        _load_id,
        _source_row,
        product_id,
        product_category_name,
        product_name_lenght,
        product_description_lenght,
        product_photos_qty,
        product_weight_g,
        product_length_cm,
        product_height_cm,
        product_width_cm,
        is_missing_category,
        is_missing_name_length,
        is_missing_description_length,
        is_missing_photos_qty,
        is_missing_weight,
        is_missing_length,
        is_missing_height,
        is_missing_width,
        is_zero_weight
    from {{ ref('stg_products') }}
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
