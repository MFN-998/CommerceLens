"""Source contracts, kept separate from future warehouse models and KPI definitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    dtype: str
    description: str
    nullable: bool = False


@dataclass(frozen=True)
class Table:
    filename: str
    grain: str
    columns: dict[str, Column]
    key: tuple[str, ...] = ()
    candidates: tuple[tuple[str, ...], ...] = ()


S = "string"
INTEGER = "Int64"
F = "Float64"
D = "datetime64[ns]"

TABLES = {
    "customers": Table(
        "olist_customers_dataset.csv",
        "One order-linked customer record per customer_id; customer_unique_id can repeat.",
        {
            "customer_id": Column(
                S, "Order-linked customer identifier; orders join on this field."
            ),
            "customer_unique_id": Column(
                S, "Cross-order customer identifier; not a unique row key."
            ),
            "customer_zip_code_prefix": Column(
                S, "Source ZIP prefix as text; no automatic padding."
            ),
            "customer_city": Column(S, "Source customer city; spelling preserved."),
            "customer_state": Column(S, "Customer Brazilian state abbreviation."),
        },
        ("customer_id",),
        (("customer_unique_id",),),
    ),
    "geolocation": Table(
        "olist_geolocation_dataset.csv",
        "One source geolocation observation; ZIP prefixes and entire rows may repeat.",
        {
            "geolocation_zip_code_prefix": Column(S, "Source ZIP prefix; not a unique join key."),
            "geolocation_lat": Column(F, "Source latitude in decimal degrees."),
            "geolocation_lng": Column(F, "Source longitude in decimal degrees."),
            "geolocation_city": Column(S, "Source city; variants are retained."),
            "geolocation_state": Column(S, "Source Brazilian state abbreviation."),
        },
        candidates=(("geolocation_zip_code_prefix",),),
    ),
    "orders": Table(
        "olist_orders_dataset.csv",
        "One order per order_id.",
        {
            "order_id": Column(S, "Order identifier."),
            "customer_id": Column(S, "Reference to customers.customer_id."),
            "order_status": Column(S, "Source lifecycle status, not an inferred completion flag."),
            "order_purchase_timestamp": Column(
                D, "Purchase timestamp; source timezone unspecified."
            ),
            "order_approved_at": Column(D, "Approval timestamp, when recorded.", True),
            "order_delivered_carrier_date": Column(
                D, "Carrier handoff timestamp, when recorded.", True
            ),
            "order_delivered_customer_date": Column(D, "Actual customer delivery timestamp.", True),
            "order_estimated_delivery_date": Column(
                D, "Estimated delivery date; not an actual event."
            ),
        },
        ("order_id",),
        (("customer_id",),),
    ),
    "order_items": Table(
        "olist_order_items_dataset.csv",
        "One order item, identified by (order_id, order_item_id).",
        {
            "order_id": Column(S, "Reference to orders.order_id."),
            "order_item_id": Column(
                INTEGER, "Item sequence within the order, not a global identifier."
            ),
            "product_id": Column(S, "Reference to products.product_id."),
            "seller_id": Column(S, "Reference to sellers.seller_id."),
            "shipping_limit_date": Column(D, "Source seller shipping deadline."),
            "price": Column(F, "Source item price in BRL; not profit or platform revenue."),
            "freight_value": Column(F, "Source item freight value in BRL."),
        },
        ("order_id", "order_item_id"),
        (("order_id",),),
    ),
    "order_payments": Table(
        "olist_order_payments_dataset.csv",
        "One payment component per (order_id, payment_sequential); orders may have many.",
        {
            "order_id": Column(S, "Reference to orders.order_id."),
            "payment_sequential": Column(INTEGER, "Payment component sequence within the order."),
            "payment_type": Column(S, "Source payment method, including not_defined if supplied."),
            "payment_installments": Column(
                INTEGER, "Source installment count; zero is retained and flagged."
            ),
            "payment_value": Column(F, "Source payment component amount in BRL."),
        },
        ("order_id", "payment_sequential"),
        (("order_id",),),
    ),
    "order_reviews": Table(
        "olist_order_reviews_dataset.csv",
        "One source review record; neither review_id nor order_id is assumed unique.",
        {
            "review_id": Column(
                S, "Source review identifier; uniqueness is profiled, not assumed."
            ),
            "order_id": Column(S, "Reference to orders.order_id; multiple reviews are retained."),
            "review_score": Column(INTEGER, "Review score on the source 1–5 scale."),
            "review_comment_title": Column(
                S, "Optional source review title; text is preserved.", True
            ),
            "review_comment_message": Column(
                S, "Optional source review text; text is preserved.", True
            ),
            "review_creation_date": Column(D, "Source review creation/survey date."),
            "review_answer_timestamp": Column(D, "Source review answer timestamp."),
        },
        key=("review_id", "order_id"),
        candidates=(("review_id",), ("order_id",)),
    ),
    "products": Table(
        "olist_products_dataset.csv",
        "One product per product_id.",
        {
            "product_id": Column(S, "Product identifier."),
            "product_category_name": Column(
                S, "Portuguese source category; may lack translation.", True
            ),
            "product_name_lenght": Column(
                INTEGER, "Source name length; original misspelled column retained.", True
            ),
            "product_description_lenght": Column(
                INTEGER, "Source description length; original name retained.", True
            ),
            "product_photos_qty": Column(INTEGER, "Source number of product photos.", True),
            "product_weight_g": Column(F, "Source weight in grams; null/zero retained.", True),
            "product_length_cm": Column(F, "Source package length in centimetres.", True),
            "product_height_cm": Column(F, "Source package height in centimetres.", True),
            "product_width_cm": Column(F, "Source package width in centimetres.", True),
        },
        ("product_id",),
    ),
    "sellers": Table(
        "olist_sellers_dataset.csv",
        "One seller per seller_id.",
        {
            "seller_id": Column(S, "Seller identifier."),
            "seller_zip_code_prefix": Column(S, "Source ZIP prefix as text; no automatic padding."),
            "seller_city": Column(S, "Source seller city; spelling preserved."),
            "seller_state": Column(S, "Seller Brazilian state abbreviation."),
        },
        ("seller_id",),
    ),
    "category_translation": Table(
        "product_category_name_translation.csv",
        "One translation per Portuguese category name; source coverage is not assumed complete.",
        {
            "product_category_name": Column(
                S, "Portuguese source category; translation lookup key."
            ),
            "product_category_name_english": Column(S, "Supplied English category translation."),
        },
        ("product_category_name",),
    ),
}

# Child table, child column, parent table, parent column, failure severity.
RELATIONSHIPS = (
    ("orders", "customer_id", "customers", "customer_id", "error"),
    ("order_items", "order_id", "orders", "order_id", "error"),
    ("order_items", "product_id", "products", "product_id", "error"),
    ("order_items", "seller_id", "sellers", "seller_id", "error"),
    ("order_payments", "order_id", "orders", "order_id", "error"),
    ("order_reviews", "order_id", "orders", "order_id", "error"),
    (
        "products",
        "product_category_name",
        "category_translation",
        "product_category_name",
        "warning",
    ),
    (
        "customers",
        "customer_zip_code_prefix",
        "geolocation",
        "geolocation_zip_code_prefix",
        "warning",
    ),
    (
        "sellers",
        "seller_zip_code_prefix",
        "geolocation",
        "geolocation_zip_code_prefix",
        "warning",
    ),
)
