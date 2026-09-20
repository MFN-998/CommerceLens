# Olist Phase 2 data-quality report

Status: **PASS_WITH_WARNINGS**. Generated: 2026-09-20T08:12:28.560132+00:00.

Source: [Olist on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), version 2; historical anonymized data, not a live business feed.

Raw bytes are preserved. Empty CSV fields become null; identifiers and free text remain strings. The UTF-8 BOM is handled during reading. No rows are dropped, imputed, or deduplicated.

Positive blocking checks: **0**. Positive warning checks: **29**. Counts can overlap.

Staging: `data/interim/olist-v2-v1`; action: `verified_existing`.

## Inventory and observed grains

| Table | Rows | Columns | Exact excess duplicates | Enforced source key |
| --- | ---: | ---: | ---: | --- |
| customers | 99,441 | 5 | 0 | customer_id |
| geolocation | 1,000,163 | 5 | 261,831 | No natural key; source row only |
| orders | 99,441 | 8 | 0 | order_id |
| order_items | 112,650 | 7 | 0 | order_id, order_item_id |
| order_payments | 103,886 | 5 | 0 | order_id, payment_sequential |
| order_reviews | 99,224 | 7 | 0 | review_id, order_id |
| products | 32,951 | 9 | 0 | product_id |
| sellers | 3,095 | 4 | 0 | seller_id |
| category_translation | 71 | 2 | 0 | product_category_name |

## Observations requiring attention

Warnings are preserved source limitations, not repaired records. They require eligibility or aggregation decisions before downstream analytics.

| Severity | Table | Check | Count | Unit | Interpretation |
| --- | --- | --- | ---: | --- | --- |
| warning | products | reference:product_category_name->category_translation.product_category_name | 13 | rows | Non-null child values without a parent match; parent uniqueness is separate. |
| warning | customers | reference:customer_zip_code_prefix->geolocation.geolocation_zip_code_prefix | 278 | rows | Non-null child values without a parent match; parent uniqueness is separate. |
| warning | sellers | reference:seller_zip_code_prefix->geolocation.geolocation_zip_code_prefix | 7 | rows | Non-null child values without a parent match; parent uniqueness is separate. |
| warning | orders | sequence:order_delivered_carrier_date_before_order_purchase_timestamp | 166 | rows | Source lifecycle reversal; retained for later eligibility decisions. |
| warning | orders | sequence:order_delivered_carrier_date_before_order_approved_at | 1,359 | rows | Source lifecycle reversal; retained for later eligibility decisions. |
| warning | orders | sequence:order_delivered_customer_date_before_order_approved_at | 61 | rows | Source lifecycle reversal; retained for later eligibility decisions. |
| warning | orders | sequence:order_delivered_customer_date_before_order_delivered_carrier_date | 23 | rows | Source lifecycle reversal; retained for later eligibility decisions. |
| warning | orders | delivered_missing:order_approved_at | 14 | rows | Delivered status without a recorded lifecycle timestamp. |
| warning | orders | delivered_missing:order_delivered_carrier_date | 2 | rows | Delivered status without a recorded lifecycle timestamp. |
| warning | orders | delivered_missing:order_delivered_customer_date | 8 | rows | Delivered status without a recorded lifecycle timestamp. |
| warning | orders | orders_without:order_items | 775 | orders | Missing child records are not orphan references; interpret by status. |
| warning | orders | orders_without:order_payments | 1 | orders | Missing child records are not orphan references; interpret by status. |
| warning | orders | orders_without:order_reviews | 768 | orders | Missing child records are not orphan references; interpret by status. |
| warning | order_reviews | multiple_reviews_per_order | 547 | orders | Preserve review/order associations; choosing one review requires a later rule. |
| warning | geolocation | outside_broad_brazil_bounds | 31 | rows | Exploratory box: latitude [-34,6], longitude [-74,-28]; not a boundary map. |
| warning | geolocation | duplicate_staging_rows | 261,831 | rows | Rows equal after typing are retained; raw duplicates are inventoried separately. |
| warning | products | missing:product_category_name | 610 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_name_lenght | 610 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_description_lenght | 610 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_photos_qty | 610 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_weight_g | 2 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_length_cm | 2 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_height_cm | 2 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | missing:product_width_cm | 2 | rows | Incomplete source product attributes remain null; no imputation. |
| warning | products | zero_weight | 4 | rows | Zero weight is not converted to missing or a made-up value. |
| warning | order_payments | zero:payment_installments | 2 | rows | Source zero retained; review before analytical use. |
| warning | order_payments | zero:payment_value | 9 | rows | Source zero retained; review before analytical use. |
| warning | order_payments | undefined_payment_type | 3 | rows | Source not_defined category is preserved. |
| warning | order_items | shipping_deadline_over_365_days | 4 | rows | Exploratory one-year threshold, not an asserted business deadline rule. |

## Missing lifecycle dates by source order status

| Status | Orders | Missing approval | Missing carrier handoff | Missing delivery |
| --- | ---: | ---: | ---: | ---: |
| approved | 2 | 0 | 2 | 2 |
| canceled | 625 | 141 | 550 | 619 |
| created | 5 | 5 | 5 | 5 |
| delivered | 96,478 | 14 | 2 | 8 |
| invoiced | 314 | 0 | 314 | 314 |
| processing | 301 | 0 | 301 | 301 |
| shipped | 1,107 | 0 | 0 | 1,107 |
| unavailable | 609 | 0 | 609 | 609 |

## Join-grain warning

275 orders have both multiple items and multiple payment components. An item/payment inner join on order_id produces 117,601 rows.

Joining item and payment rows on order_id multiplies rows. Aggregate each to an explicitly chosen grain in Phase 3 before combining monetary measures.

## Interpretation and limitations

- Optional review text is measured in the dictionary, not treated as an error.
- Missing event timestamps are contextual: non-delivered orders may not have delivery dates; delivered orders missing them are explicitly flagged.
- Observed (review_id, order_id) uniqueness/null checks passed. Individual-key observations: review_id: 1,603 rows in repeated keys, order_id: 1,098 rows in repeated keys. All review records are retained.
- Customer identity across orders uses customer_unique_id, whereas the source order relationship uses customer_id.
- Geography needs a documented unique ZIP mapping before joins. The broad Brazil coordinate box is an exploratory screen, not a geographic boundary test.
- All source timestamps are timezone-naive because the source does not declare a timezone. No UTC conversion is invented.
- Monetary amounts remain source numeric values; this phase defines no GMV, revenue, profit, or payment-reconciliation business metric.
- FAIL blocks promotion. PASS_WITH_WARNINGS permits the faithful local staging snapshot, not unrestricted analytical use of all rows.

The [JSON report](data-quality-report.json) includes checks, hashes, column missingness/ranges, candidate-key counts, and categorical domains. See the [initial dictionary](data_dictionary/initial.md) for column meanings.
