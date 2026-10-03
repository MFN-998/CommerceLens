-- One retained source product_id, including missing and untranslated categories.
-- The unique literal category lookup adds labels without repairing source fields.
select
    p._load_id,
    p._source_row,
    p.product_id,
    p.product_category_name,
    p.product_name_lenght,
    p.product_description_lenght,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.is_missing_category,
    p.is_missing_name_length,
    p.is_missing_description_length,
    p.is_missing_photos_qty,
    p.is_missing_weight,
    p.is_missing_length,
    p.is_missing_height,
    p.is_missing_width,
    p.is_zero_weight,
    t.product_category_name_english,
    p.product_category_name is not null
        and t.product_category_name is null as is_untranslated_category
from {{ ref('stg_products') }} p
left join {{ ref('stg_category_translation') }} t
    on p.product_category_name collate "C" = t.product_category_name collate "C"
