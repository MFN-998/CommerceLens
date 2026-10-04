{{ config(severity='error', store_failures=false) }}
-- Compare all fields as a literal multiset: conserve cents, warnings and lineage.
with expected as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        payment_sequential,
        payment_type collate "C" as payment_type,
        payment_installments,
        payment_value,
        is_zero_installments,
        is_zero_payment_value,
        is_undefined_payment_type
    from {{ ref('stg_order_payments') }}
), actual as (
    select
        _load_id,
        _source_row,
        order_id collate "C" as order_id,
        payment_sequential,
        payment_type collate "C" as payment_type,
        payment_installments,
        payment_value,
        is_zero_installments,
        is_zero_payment_value,
        is_undefined_payment_type
    from {{ ref('fact_payments') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), diagnostics as (
    select (select count(*) from expected) as source_payment_count,
        (select count(*) from actual) as fact_payment_count,
        (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from diagnostics
where source_payment_count <> fact_payment_count
    or missing_or_changed_count > 0 or extra_or_changed_count > 0
