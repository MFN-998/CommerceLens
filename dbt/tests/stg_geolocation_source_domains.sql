{{ config(severity='error', store_failures=false) }}

-- Mandatory source formats/global coordinate ranges fail validation. The
-- exploratory Brazil box is not a blocking domain and never removes outliers.
-- Return only an aggregate diagnostic, never source locations or identifiers.
select count(*) as invalid_source_value_rows
from {{ ref('stg_geolocation') }}
where _load_id is null
    or _source_row is null
    or _source_row < 1
    or geolocation_zip_code_prefix is null
    or geolocation_zip_code_prefix !~ '^[0-9]{1,5}$'
    or geolocation_lat is null
    or geolocation_lat not between -90 and 90
    or geolocation_lng is null
    or geolocation_lng not between -180 and 180
    or geolocation_city is null
    or geolocation_state is null
    or geolocation_state not in (
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
        'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
        'SP', 'SE', 'TO'
    )
having count(*) > 0
