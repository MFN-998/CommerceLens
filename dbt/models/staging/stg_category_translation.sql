-- One row per original Portuguese category; English translations may repeat.
-- Convert only exactly empty source text to null. Preserve literal spelling,
-- whitespace, accents, case and lineage; do not invent labels or deduplicate.
select
    _load_id,
    _source_row,
    nullif(product_category_name, '') as product_category_name,
    nullif(product_category_name_english, '') as product_category_name_english
from {{ source('raw', 'category_translation') }}
