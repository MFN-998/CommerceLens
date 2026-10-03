-- One retained source seller_id. A unique ZIP-domain join preserves the grain.
-- Missing geolocation is legitimate false coverage; a missing dimension row
-- leaves coverage NULL and fails required/reference tests instead of hiding it.
select
    s._load_id,
    s._source_row,
    s.seller_id,
    s.seller_zip_code_prefix,
    s.seller_city,
    s.seller_state,
    l.has_geolocation
from {{ ref('stg_sellers') }} s
left join {{ ref('dim_location') }} l
    on s.seller_zip_code_prefix collate "C" = l.zip_code_prefix collate "C"
