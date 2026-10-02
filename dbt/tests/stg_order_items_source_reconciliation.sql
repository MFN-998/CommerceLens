{{ config(severity='error', store_failures=false) }}

-- Full row multiset comparison catches substitutions and multiplicity changes,
-- including count-preserving edits, without exposing identifiers or source text.
with expected as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        {{ commercelens_nullable_bigint("nullif(order_item_id, '')") }} as order_item_id,
        nullif(product_id, '') as product_id,
        nullif(seller_id, '') as seller_id,
        {{ commercelens_nullable_timestamp("nullif(shipping_limit_date, '')") }} as shipping_limit_date,
        {{ commercelens_nullable_money("nullif(price, '')") }} as price,
        {{ commercelens_nullable_money("nullif(freight_value, '')") }} as freight_value
    from {{ source('raw', 'order_items') }}
),
actual as (
    select
        _load_id,
        _source_row,
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value
    from {{ ref('stg_order_items') }}
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
