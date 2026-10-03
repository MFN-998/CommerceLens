{{ config(severity='error', store_failures=false) }}
-- Independently derive the literal identity domain from staging. Multisets in
-- both directions detect missing, extra, changed and duplicated output identities.
with expected as (
    select distinct customer_unique_id collate "C" as customer_unique_id
    from {{ ref('stg_customers') }}
), actual as (
    select customer_unique_id collate "C" as customer_unique_id
    from {{ ref('dim_customer') }}
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
