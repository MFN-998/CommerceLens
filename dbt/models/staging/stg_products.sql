-- Retain one source row per product_id; do not join translations until dim_product.
-- Only exactly empty source text becomes NULL. Missing flags describe the source,
-- independently of cast failures, which the blocking source-domain test reports.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(product_id, '') as product_id,
        nullif(product_category_name, '') as product_category_name,
        nullif(product_name_lenght, '') as product_name_lenght,
        nullif(product_description_lenght, '') as product_description_lenght,
        nullif(product_photos_qty, '') as product_photos_qty,
        nullif(product_weight_g, '') as product_weight_g,
        nullif(product_length_cm, '') as product_length_cm,
        nullif(product_height_cm, '') as product_height_cm,
        nullif(product_width_cm, '') as product_width_cm
    from {{ source('raw', 'products') }}
),
typed as (
    select
        _load_id,
        _source_row,
        product_id,
        product_category_name,
        {{ commercelens_nullable_bigint('product_name_lenght') }} as product_name_lenght,
        {{ commercelens_nullable_bigint('product_description_lenght') }} as product_description_lenght,
        {{ commercelens_nullable_bigint('product_photos_qty') }} as product_photos_qty,
        {{ commercelens_nullable_double('product_weight_g') }} as product_weight_g,
        {{ commercelens_nullable_double('product_length_cm') }} as product_length_cm,
        {{ commercelens_nullable_double('product_height_cm') }} as product_height_cm,
        {{ commercelens_nullable_double('product_width_cm') }} as product_width_cm,
        product_category_name is null as is_missing_category,
        product_name_lenght is null as is_missing_name_length,
        product_description_lenght is null as is_missing_description_length,
        product_photos_qty is null as is_missing_photos_qty,
        product_weight_g is null as is_missing_weight,
        product_length_cm is null as is_missing_length,
        product_height_cm is null as is_missing_height,
        product_width_cm is null as is_missing_width
    from normalized
)

select
    *,
    coalesce(product_weight_g = 0, false) as is_zero_weight
from typed
