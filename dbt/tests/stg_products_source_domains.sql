{{ config(severity='error', store_failures=false) }}

-- Phase 2 ID/ordinal/nonnegative rules plus numeric parse failures. Optional
-- source missingness is valid. Invalid nonempty values must never pass as NULL.
-- Return aggregate diagnostics only, without identifiers or source text.
select count(*) as invalid_source_value_rows
from {{ ref('stg_products') }} as staged
left join {{ source('raw', 'products') }} as original
    on staged._load_id = original._load_id
    and staged._source_row = original._source_row
where staged.product_id is null
    or staged.product_id !~ '^[0-9a-f]{32}$'
    or staged._source_row is null
    or staged._source_row < 1
    or staged.product_name_lenght < 0
    or staged.product_description_lenght < 0
    or staged.product_photos_qty < 0
    or staged.product_weight_g < 0
    or staged.product_length_cm < 0
    or staged.product_height_cm < 0
    or staged.product_width_cm < 0
    or staged.product_weight_g > cast('1.7976931348623157e308' as double precision)
    or staged.product_length_cm > cast('1.7976931348623157e308' as double precision)
    or staged.product_height_cm > cast('1.7976931348623157e308' as double precision)
    or staged.product_width_cm > cast('1.7976931348623157e308' as double precision)
    or (nullif(original.product_name_lenght, '') is not null and staged.product_name_lenght is null)
    or (nullif(original.product_description_lenght, '') is not null and staged.product_description_lenght is null)
    or (nullif(original.product_photos_qty, '') is not null and staged.product_photos_qty is null)
    or (nullif(original.product_weight_g, '') is not null and staged.product_weight_g is null)
    or (nullif(original.product_length_cm, '') is not null and staged.product_length_cm is null)
    or (nullif(original.product_height_cm, '') is not null and staged.product_height_cm is null)
    or (nullif(original.product_width_cm, '') is not null and staged.product_width_cm is null)
having count(*) > 0
