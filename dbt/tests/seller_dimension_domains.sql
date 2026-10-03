{{ config(severity='error', store_failures=false) }}
-- Validate retained fields without trimming, repairing or filtering sellers.
select count(*) as invalid_seller_dimension_rows
from {{ ref('dim_seller') }}
where seller_id is null or seller_id collate "C" !~ '^[0-9a-f]{32}$'
    or seller_zip_code_prefix is null
    or seller_zip_code_prefix collate "C" !~ '^[0-9]{1,5}$'
    or _source_row is null or _source_row < 1
    or seller_state is null
    or seller_state not in (
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
        'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
        'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
    )
having count(*) > 0
