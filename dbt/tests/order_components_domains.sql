{{ config(severity='error', store_failures=false) }}
-- Validate presence, missingness and retained component-warning bounds.
select count(*) as invalid_order_component_rows
from {{ ref('mart_order_components') }}
where order_id is null
    or order_id !~ '^[0-9a-f]{32}$'
    or item_count is null
    or item_count < 0
    or has_items is distinct from (item_count > 0)
    or shipping_before_purchase_count is null
    or shipping_before_purchase_count not between 0 and item_count
    or shipping_beyond_365_days_count is null
    or shipping_beyond_365_days_count not between 0 and item_count
    or payment_count is null
    or payment_count < 0
    or has_payments is distinct from (payment_count > 0)
    or zero_installments_count is null
    or zero_installments_count not between 0 and payment_count
    or zero_payment_value_count is null
    or zero_payment_value_count not between 0 and payment_count
    or undefined_payment_type_count is null
    or undefined_payment_type_count not between 0 and payment_count
    or review_count is null
    or review_count < 0
    or has_reviews is distinct from (review_count > 0)
    or answer_before_creation_count is null
    or answer_before_creation_count not between 0 and review_count
    or has_multiple_reviews is distinct from (review_count > 1)
    or (item_count = 0 and source_price_sum is not null)
    or (item_count > 0 and (source_price_sum is null or source_price_sum < 0 or source_price_sum > item_count * 9999999999999999.99::numeric))
    or (item_count = 0 and source_freight_sum is not null)
    or (item_count > 0 and (source_freight_sum is null or source_freight_sum < 0 or source_freight_sum > item_count * 9999999999999999.99::numeric))
    or (payment_count = 0 and source_payment_sum is not null)
    or (payment_count > 0 and (source_payment_sum is null or source_payment_sum < 0 or source_payment_sum > payment_count * 9999999999999999.99::numeric))
having count(*) > 0
