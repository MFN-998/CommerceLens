# Initial Olist source and staging dictionary

Observed against pinned Olist version 2. These are source contracts, not the Phase 3 warehouse design. All source names, including `lenght`, are preserved.

Every staging table adds `_source_row` (nullable integer dtype, no null values): the 1-based CSV data-record ordinal, excluding the header. It is not a physical line number because review text can contain line breaks.

## customers

One order-linked customer record per customer_id; customer_unique_id can repeat.

Source: `olist_customers_dataset.csv` — 99,441 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| customer_id | string | False | 0 | 99,441 | Order-linked customer identifier; orders join on this field. |
| customer_unique_id | string | False | 0 | 96,096 | Cross-order customer identifier; not a unique row key. |
| customer_zip_code_prefix | string | False | 0 | 14,994 | Source ZIP prefix as text; no automatic padding. |
| customer_city | string | False | 0 | 4,119 | Source customer city; spelling preserved. |
| customer_state | string | False | 0 | 27 | Customer Brazilian state abbreviation. |

Observed keys:

- `customer_id`: 99,441 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
- `customer_unique_id`: 96,096 distinct keys, 6,342 rows in repeated keys, 0 null-key rows; enforced: False.

## geolocation

One source geolocation observation; ZIP prefixes and entire rows may repeat.

Source: `olist_geolocation_dataset.csv` — 1,000,163 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| geolocation_zip_code_prefix | string | False | 0 | 19,015 | Source ZIP prefix; not a unique join key. |
| geolocation_lat | Float64 | False | 0 | 717,360 | Source latitude in decimal degrees. |
| geolocation_lng | Float64 | False | 0 | 717,613 | Source longitude in decimal degrees. |
| geolocation_city | string | False | 0 | 8,011 | Source city; variants are retained. |
| geolocation_state | string | False | 0 | 27 | Source Brazilian state abbreviation. |

Observed keys:

- `geolocation_zip_code_prefix`: 19,015 distinct keys, 999,120 rows in repeated keys, 0 null-key rows; enforced: False.

## orders

One order per order_id.

Source: `olist_orders_dataset.csv` — 99,441 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| order_id | string | False | 0 | 99,441 | Order identifier. |
| customer_id | string | False | 0 | 99,441 | Reference to customers.customer_id. |
| order_status | string | False | 0 | 8 | Source lifecycle status, not an inferred completion flag. |
| order_purchase_timestamp | datetime64[ns] | False | 0 | 98,875 | Purchase timestamp; source timezone unspecified. |
| order_approved_at | datetime64[ns] | True | 160 | 90,733 | Approval timestamp, when recorded. |
| order_delivered_carrier_date | datetime64[ns] | True | 1,783 | 81,018 | Carrier handoff timestamp, when recorded. |
| order_delivered_customer_date | datetime64[ns] | True | 2,965 | 95,664 | Actual customer delivery timestamp. |
| order_estimated_delivery_date | datetime64[ns] | False | 0 | 459 | Estimated delivery date; not an actual event. |

Observed keys:

- `order_id`: 99,441 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
- `customer_id`: 99,441 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: False.

## order_items

One order item, identified by (order_id, order_item_id).

Source: `olist_order_items_dataset.csv` — 112,650 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| order_id | string | False | 0 | 98,666 | Reference to orders.order_id. |
| order_item_id | Int64 | False | 0 | 21 | Item sequence within the order, not a global identifier. |
| product_id | string | False | 0 | 32,951 | Reference to products.product_id. |
| seller_id | string | False | 0 | 3,095 | Reference to sellers.seller_id. |
| shipping_limit_date | datetime64[ns] | False | 0 | 93,318 | Source seller shipping deadline. |
| price | Float64 | False | 0 | 5,968 | Source item price in BRL; not profit or platform revenue. |
| freight_value | Float64 | False | 0 | 6,999 | Source item freight value in BRL. |

Observed keys:

- `order_id, order_item_id`: 112,650 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
- `order_id`: 98,666 distinct keys, 23,787 rows in repeated keys, 0 null-key rows; enforced: False.

## order_payments

One payment component per (order_id, payment_sequential); orders may have many.

Source: `olist_order_payments_dataset.csv` — 103,886 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| order_id | string | False | 0 | 99,440 | Reference to orders.order_id. |
| payment_sequential | Int64 | False | 0 | 29 | Payment component sequence within the order. |
| payment_type | string | False | 0 | 5 | Source payment method, including not_defined if supplied. |
| payment_installments | Int64 | False | 0 | 24 | Source installment count; zero is retained and flagged. |
| payment_value | Float64 | False | 0 | 29,077 | Source payment component amount in BRL. |

Observed keys:

- `order_id, payment_sequential`: 103,886 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
- `order_id`: 99,440 distinct keys, 7,407 rows in repeated keys, 0 null-key rows; enforced: False.

## order_reviews

One source review record; neither review_id nor order_id is assumed unique.

Source: `olist_order_reviews_dataset.csv` — 99,224 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| review_id | string | False | 0 | 98,410 | Source review identifier; uniqueness is profiled, not assumed. |
| order_id | string | False | 0 | 98,673 | Reference to orders.order_id; multiple reviews are retained. |
| review_score | Int64 | False | 0 | 5 | Review score on the source 1–5 scale. |
| review_comment_title | string | True | 87,656 | 4,527 | Optional source review title; text is preserved. |
| review_comment_message | string | True | 58,247 | 36,159 | Optional source review text; text is preserved. |
| review_creation_date | datetime64[ns] | False | 0 | 636 | Source review creation/survey date. |
| review_answer_timestamp | datetime64[ns] | False | 0 | 98,248 | Source review answer timestamp. |

Observed keys:

- `review_id, order_id`: 99,224 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
- `review_id`: 98,410 distinct keys, 1,603 rows in repeated keys, 0 null-key rows; enforced: False.
- `order_id`: 98,673 distinct keys, 1,098 rows in repeated keys, 0 null-key rows; enforced: False.

## products

One product per product_id.

Source: `olist_products_dataset.csv` — 32,951 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| product_id | string | False | 0 | 32,951 | Product identifier. |
| product_category_name | string | True | 610 | 73 | Portuguese source category; may lack translation. |
| product_name_lenght | Int64 | True | 610 | 66 | Source name length; original misspelled column retained. |
| product_description_lenght | Int64 | True | 610 | 2,960 | Source description length; original name retained. |
| product_photos_qty | Int64 | True | 610 | 19 | Source number of product photos. |
| product_weight_g | Float64 | True | 2 | 2,204 | Source weight in grams; null/zero retained. |
| product_length_cm | Float64 | True | 2 | 99 | Source package length in centimetres. |
| product_height_cm | Float64 | True | 2 | 102 | Source package height in centimetres. |
| product_width_cm | Float64 | True | 2 | 95 | Source package width in centimetres. |

Observed keys:

- `product_id`: 32,951 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.

## sellers

One seller per seller_id.

Source: `olist_sellers_dataset.csv` — 3,095 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| seller_id | string | False | 0 | 3,095 | Seller identifier. |
| seller_zip_code_prefix | string | False | 0 | 2,246 | Source ZIP prefix as text; no automatic padding. |
| seller_city | string | False | 0 | 611 | Source seller city; spelling preserved. |
| seller_state | string | False | 0 | 23 | Seller Brazilian state abbreviation. |

Observed keys:

- `seller_id`: 3,095 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.

## category_translation

One translation per Portuguese category name; source coverage is not assumed complete.

Source: `product_category_name_translation.csv` — 71 records.

| Column | Staging type | Nullable | Observed nulls | Distinct values | Meaning |
| --- | --- | --- | ---: | ---: | --- |
| product_category_name | string | False | 0 | 71 | Portuguese source category; translation lookup key. |
| product_category_name_english | string | False | 0 | 71 | Supplied English category translation. |

Observed keys:

- `product_category_name`: 71 distinct keys, 0 rows in repeated keys, 0 null-key rows; enforced: True.
