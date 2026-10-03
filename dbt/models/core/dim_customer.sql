-- One literal cross-order identity across source customers, addresses and loads.
-- Retain null/invalid identities for validation; do not select a current address.
select distinct customer_unique_id collate "C" as customer_unique_id
from {{ ref('stg_customers') }}
