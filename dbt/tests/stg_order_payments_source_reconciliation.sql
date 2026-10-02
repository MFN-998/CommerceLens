{{ config(severity='error', store_failures=false) }}

-- Compare the complete multiset: source attributes, lineage and all three flags.
-- Count-preserving edits/duplicate substitutions must fail without exposing rows.
with expected_typed as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        {{ commercelens_nullable_bigint("nullif(payment_sequential, '')") }} as payment_sequential,
        nullif(payment_type, '') as payment_type,
        {{ commercelens_nullable_bigint("nullif(payment_installments, '')") }} as payment_installments,
        {{ commercelens_nullable_money("nullif(payment_value, '')") }} as payment_value
    from {{ source('raw', 'order_payments') }}
),
expected as (
    select
        *,
        coalesce(payment_installments = 0, false) as is_zero_installments,
        coalesce(payment_value = 0, false) as is_zero_payment_value,
        coalesce(payment_type = 'not_defined', false) as is_undefined_payment_type
    from expected_typed
),
actual as (
    select
        _load_id,
        _source_row,
        order_id,
        payment_sequential,
        payment_type,
        payment_installments,
        payment_value,
        is_zero_installments,
        is_zero_payment_value,
        is_undefined_payment_type
    from {{ ref('stg_order_payments') }}
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
