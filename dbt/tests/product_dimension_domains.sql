{{ config(severity='error', store_failures=false) }}
-- Numeric and original missingness domains are validated upstream. Here, retain
-- source fields and block invalid product identity/ordinal or translation state.
select count(*) as invalid_product_dimension_rows
from {{ ref('dim_product') }}
where product_id is null or product_id collate "C" !~ '^[0-9a-f]{32}$'
    or _source_row is null or _source_row < 1
    or is_untranslated_category is null
    or is_missing_category is distinct from (product_category_name is null)
    or (product_category_name is null and (
        product_category_name_english is not null or is_untranslated_category
    ))
    or (product_category_name is not null and (
        (product_category_name_english is null and not is_untranslated_category)
        or (product_category_name_english is not null and is_untranslated_category)
    ))
having count(*) > 0
