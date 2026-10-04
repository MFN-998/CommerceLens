{{ config(severity='error', store_failures=false) }}
-- Required literal identity/ZIP parents must exist. Geography coverage does not
-- affect reference validity, and missing parents must never filter source records.
with missing_references as (
    select (
        select count(*)
        from {{ ref('int_order_customers') }} c
        where not exists (
            select 1 from {{ ref('dim_customer') }} d
            where c.customer_unique_id collate "C" = d.customer_unique_id collate "C"
        )
    ) as missing_customer_identity_count, (
        select count(*)
        from {{ ref('int_order_customers') }} c
        where not exists (
            select 1 from {{ ref('dim_location') }} l
            where c.customer_zip_code_prefix collate "C" = l.zip_code_prefix collate "C"
        )
    ) as missing_location_count
)
select * from missing_references
where missing_customer_identity_count > 0 or missing_location_count > 0
