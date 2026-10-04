{{ config(severity='error', store_failures=false) }}
-- All source fields and lineage are compared as full multisets. Literal C text
-- comparison preserves address and identity spelling, including case/whitespace.
with expected as (
    select
        _load_id,
        _source_row,
        customer_id collate "C" as customer_id,
        customer_unique_id collate "C" as customer_unique_id,
        customer_zip_code_prefix collate "C" as customer_zip_code_prefix,
        customer_city collate "C" as customer_city,
        customer_state collate "C" as customer_state
    from {{ ref('stg_customers') }}
), actual as (
    select
        _load_id,
        _source_row,
        customer_id collate "C" as customer_id,
        customer_unique_id collate "C" as customer_unique_id,
        customer_zip_code_prefix collate "C" as customer_zip_code_prefix,
        customer_city collate "C" as customer_city,
        customer_state collate "C" as customer_state
    from {{ ref('int_order_customers') }}
), missing_or_changed as (
    select * from expected
    except all
    select * from actual
), extra_or_changed as (
    select * from actual
    except all
    select * from expected
), differences as (
    select (select count(*) from missing_or_changed) as missing_or_changed_count,
        (select count(*) from extra_or_changed) as extra_or_changed_count
)
select * from differences
where missing_or_changed_count > 0 or extra_or_changed_count > 0
