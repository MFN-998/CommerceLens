-- Retain every source component at (order_id, payment_sequential), without joins.
-- Zero installments/value and literal not_defined remain source warnings; no
-- imputation, order-level aggregation or analytical eligibility is introduced.
-- Missing/rejected mandatory input remains queryable and blocks acceptance.
with normalized as (
    select
        _load_id,
        _source_row,
        nullif(order_id, '') as order_id,
        nullif(payment_sequential, '') as payment_sequential,
        nullif(payment_type, '') as payment_type,
        nullif(payment_installments, '') as payment_installments,
        nullif(payment_value, '') as payment_value
    from {{ source('raw', 'order_payments') }}
),
typed as (
    select
        _load_id,
        _source_row,
        order_id,
        {{ commercelens_nullable_bigint('payment_sequential') }} as payment_sequential,
        payment_type,
        {{ commercelens_nullable_bigint('payment_installments') }} as payment_installments,
        {{ commercelens_nullable_money('payment_value') }} as payment_value
    from normalized
)

select
    *,
    coalesce(payment_installments = 0, false) as is_zero_installments,
    coalesce(payment_value = 0, false) as is_zero_payment_value,
    coalesce(payment_type = 'not_defined', false) as is_undefined_payment_type
from typed
