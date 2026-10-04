{{ config(severity='error', store_failures=false) }}
-- Invalid mandatory input fails without dropping components or exposing records.
-- Warning flags retain their accepted staging meaning; zero is not absence.
select count(*) as invalid_payment_fact_rows
from {{ ref('fact_payments') }}
where _load_id is null
    or _source_row is null or _source_row < 1
    or order_id is null or order_id !~ '^[0-9a-f]{32}$'
    or payment_sequential is null or payment_sequential < 1
    or payment_type is null
    or payment_type collate "C" not in ('credit_card', 'boleto', 'voucher', 'debit_card', 'not_defined')
    or payment_installments is null or payment_installments < 0
    or payment_value is null or payment_value < 0
    or payment_value > 9999999999999999.99
    or is_zero_installments is distinct from coalesce(payment_installments = 0, false)
    or is_zero_payment_value is distinct from coalesce(payment_value = 0, false)
    or is_undefined_payment_type is distinct from coalesce(payment_type collate "C" = 'not_defined', false)
having count(*) > 0
