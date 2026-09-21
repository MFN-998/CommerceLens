-- Run through the migration runner, inside its transaction and advisory lock.
-- Creator-specific defaults from 0001 give the loader SELECT/INSERT on raw
-- tables, the transformer SELECT, and no access to PUBLIC or Data API roles.
SET LOCAL search_path = pg_catalog;
SET LOCAL ROLE commercelens_owner;

-- One immutable provenance record per verified source snapshot. The loader
-- inserts this record before COPY so immediate foreign keys can be checked.
-- Registry evidence contains the expected validated file counts, digests and
-- exact monetary totals. Registry insertion, all nine COPY operations and
-- reconciliation share one transaction: incomplete snapshots never commit.
-- Routine roles cannot UPDATE/DELETE the registry or source rows.
CREATE TABLE ops.source_loads (
    load_id uuid PRIMARY KEY,
    source_fingerprint text NOT NULL UNIQUE
        CHECK (source_fingerprint ~ '^[0-9a-f]{64}$'),
    dataset_handle text NOT NULL
        CHECK (dataset_handle = 'olistbr/brazilian-ecommerce/versions/2'),
    contract_version integer NOT NULL CHECK (contract_version = 1),
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    source_files jsonb NOT NULL CHECK (jsonb_typeof(source_files) = 'object'),
    loaded_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_by text NOT NULL DEFAULT session_user
);

-- Grant registry access only, never migration-ledger access. Server-populated
-- attribution/timestamp columns are excluded from the loader's INSERT grant.
GRANT USAGE ON SCHEMA ops TO commercelens_loader, commercelens_transformer;
GRANT SELECT ON TABLE ops.source_loads
    TO commercelens_loader, commercelens_transformer;
GRANT INSERT (
    load_id, source_fingerprint, dataset_handle,
    contract_version, manifest_sha256, source_files
) ON TABLE ops.source_loads TO commercelens_loader;

-- Raw landing preserves parsed CSV strings, including empty strings. NULL is
-- forbidden even for source fields that will become nullable in staging.
-- _source_row is a one-based logical CSV record ordinal, excluding the header;
-- a quoted multiline review is one record, not several physical lines.
-- Amounts remain source text here; exact decimal validation/reconciliation
-- precedes later numeric(18,2) staging casts. No binary floats define money.
-- Only lineage keys are indexed; source/natural grains are validated by the
-- loader and later models, so repeated geography observations remain intact.
CREATE TABLE raw.customers (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    customer_id text NOT NULL,
    customer_unique_id text NOT NULL,
    customer_zip_code_prefix text NOT NULL,
    customer_city text NOT NULL,
    customer_state text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.geolocation (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    geolocation_zip_code_prefix text NOT NULL,
    geolocation_lat text NOT NULL,
    geolocation_lng text NOT NULL,
    geolocation_city text NOT NULL,
    geolocation_state text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.orders (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    order_id text NOT NULL,
    customer_id text NOT NULL,
    order_status text NOT NULL,
    order_purchase_timestamp text NOT NULL,
    order_approved_at text NOT NULL,
    order_delivered_carrier_date text NOT NULL,
    order_delivered_customer_date text NOT NULL,
    order_estimated_delivery_date text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.order_items (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    order_id text NOT NULL,
    order_item_id text NOT NULL,
    product_id text NOT NULL,
    seller_id text NOT NULL,
    shipping_limit_date text NOT NULL,
    price text NOT NULL,
    freight_value text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.order_payments (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    order_id text NOT NULL,
    payment_sequential text NOT NULL,
    payment_type text NOT NULL,
    payment_installments text NOT NULL,
    payment_value text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.order_reviews (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    review_id text NOT NULL,
    order_id text NOT NULL,
    review_score text NOT NULL,
    review_comment_title text NOT NULL,
    review_comment_message text NOT NULL,
    review_creation_date text NOT NULL,
    review_answer_timestamp text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.products (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    product_id text NOT NULL,
    product_category_name text NOT NULL,
    product_name_lenght text NOT NULL,
    product_description_lenght text NOT NULL,
    product_photos_qty text NOT NULL,
    product_weight_g text NOT NULL,
    product_length_cm text NOT NULL,
    product_height_cm text NOT NULL,
    product_width_cm text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.sellers (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    seller_id text NOT NULL,
    seller_zip_code_prefix text NOT NULL,
    seller_city text NOT NULL,
    seller_state text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

CREATE TABLE raw.category_translation (
    _load_id uuid NOT NULL REFERENCES ops.source_loads (load_id) NOT DEFERRABLE,
    _source_row bigint NOT NULL CHECK (_source_row > 0),
    product_category_name text NOT NULL,
    product_category_name_english text NOT NULL,
    PRIMARY KEY (_load_id, _source_row)
);

RESET ROLE;
