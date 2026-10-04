{{ config(severity='error', store_failures=false) }}
-- Independent long-form union/group oracle, not the model's three-join construction.
-- Per-order comparison catches redistribution that global totals alone would miss.
with source_components as (
    select order_id collate "C" as order_id, 'items'::text as component,
        price as amount_a, freight_value as amount_b,
        case when is_shipping_before_purchase then 1 else 0 end as warning_a,
        case when is_shipping_beyond_365_days then 1 else 0 end as warning_b,
        0 as warning_c
    from {{ ref('fact_order_items') }}
    union all
    select order_id collate "C", 'payments', payment_value, null::numeric,
        case when is_zero_installments then 1 else 0 end,
        case when is_zero_payment_value then 1 else 0 end,
        case when is_undefined_payment_type then 1 else 0 end
    from {{ ref('fact_payments') }}
    union all
    select order_id collate "C", 'reviews', null::numeric, null::numeric,
        case when is_answer_before_creation then 1 else 0 end, 0, 0
    from {{ ref('fact_reviews') }}
), expected as materialized (
    select order_id collate "C" as order_id, component collate "C" as component,
        count(*) as component_count, sum(amount_a) as amount_a, sum(amount_b) as amount_b,
        cast(sum(warning_a) as bigint) as warning_a,
        cast(sum(warning_b) as bigint) as warning_b,
        cast(sum(warning_c) as bigint) as warning_c
    from source_components group by order_id collate "C", component collate "C"
), mart as materialized (
    select order_id collate "C" as order_id, item_count, source_price_sum, source_freight_sum,
        shipping_before_purchase_count, shipping_beyond_365_days_count, has_items,
        payment_count, source_payment_sum, zero_installments_count, zero_payment_value_count,
        undefined_payment_type_count, has_payments, review_count, answer_before_creation_count, has_reviews
    from {{ ref('mart_order_components') }}
), actual as materialized (
    select order_id, 'items'::text collate "C" as component, item_count as component_count,
        source_price_sum as amount_a, source_freight_sum as amount_b,
        shipping_before_purchase_count as warning_a, shipping_beyond_365_days_count as warning_b,
        0::bigint as warning_c from mart where has_items
    union all
    select order_id, 'payments', payment_count, source_payment_sum, null::numeric,
        zero_installments_count, zero_payment_value_count, undefined_payment_type_count
    from mart where has_payments
    union all
    select order_id, 'reviews', review_count, null::numeric, null::numeric,
        answer_before_creation_count, 0::bigint, 0::bigint from mart where has_reviews
), missing_or_changed as (
    select * from expected except all select * from actual
), extra_or_changed as (
    select * from actual except all select * from expected
)
select (select count(*) from missing_or_changed) as missing_or_changed_count,
    (select count(*) from extra_or_changed) as extra_or_changed_count
where exists (select 1 from missing_or_changed) or exists (select 1 from extra_or_changed)
