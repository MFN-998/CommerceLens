{{ config(severity='error', store_failures=false) }}
-- Compare every staging field plus literal lookup output in both multiset
-- directions. Independent source/output row counts also reject lookup fanout.
with expected as (
    select
        p._load_id,
        p._source_row,
        p.product_id collate "C" as product_id,
        p.product_category_name collate "C" as product_category_name,
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
        t.product_category_name_english collate "C" as product_category_name_english,
        p.product_category_name is not null
            and t.product_category_name is null as is_untranslated_category
    from {{ ref('stg_products') }} p
    left join {{ ref('stg_category_translation') }} t
        on p.product_category_name collate "C" = t.product_category_name collate "C"
), actual as (
    select
        _load_id,
        _source_row,
        product_id collate "C" as product_id,
        product_category_name collate "C" as product_category_name,
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
        is_zero_weight,
        product_category_name_english collate "C" as product_category_name_english,
        is_untranslated_category
    from {{ ref('dim_product') }}
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
        (select count(*) from extra_or_changed) as extra_or_changed_count,
        (select count(*) from {{ ref('stg_products') }}) as source_row_count,
        (select count(*) from actual) as dimension_row_count
)
select * from differences
where missing_or_changed_count > 0 or extra_or_changed_count > 0
    or source_row_count <> dimension_row_count
