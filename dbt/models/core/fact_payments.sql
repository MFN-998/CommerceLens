-- One source-preserving payment component at (order_id, payment_sequential).
-- Retain accepted types, both lineage fields and all three source warnings.
-- Order membership is validated separately; no join, filter or aggregation.
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
