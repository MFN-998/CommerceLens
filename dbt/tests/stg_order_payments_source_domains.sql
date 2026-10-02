{{ config(severity='error', store_failures=false) }}

-- Missing/invalid mandatory attributes block acceptance while retaining rows.
-- Source zero installments/amount and not_defined are warnings, not errors.
-- Return aggregate diagnostics only, without identifiers or source text.
select count(*) as invalid_source_value_rows
from {{ ref('stg_order_payments') }}
where _load_id is null
    or _source_row is null
    or _source_row < 1
    or order_id is null
    or order_id !~ '^[0-9a-f]{32}$'
    or payment_sequential is null
    or payment_sequential < 1
    or payment_type is null
    or payment_type not in ('credit_card', 'boleto', 'voucher', 'debit_card', 'not_defined')
    or payment_installments is null
    or payment_installments < 0
    or payment_value is null
    or payment_value < 0
    or payment_value > 9999999999999999.99
having count(*) > 0
