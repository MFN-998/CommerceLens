"""Checksum-guarded, aggregate-only Phase 4 exploration of retained Olist CSVs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.validation.contracts import TABLES
from src.warehouse.source import iter_source_rows, parse_money, prepare_source


def cents(value: str) -> int:
    return int(parse_money(value) * 100)


def ratio(n: int, d: int) -> float | None:
    return n / d if d else None


def wilson(n: int, d: int) -> list[float] | None:
    """Descriptive 95% Wilson bounds, without random-sample/causal claims."""
    if not 0 <= n <= d:
        raise ValueError("Invalid binary counts")
    if not d:
        return None
    z = 1.959963984540054
    p = n / d
    scale = 1 + z * z / d
    center = (p + z * z / (2 * d)) / scale
    half = z * math.sqrt(p * (1 - p) / d + z * z / (4 * d * d)) / scale
    return [center - half, center + half]


def join(left: pd.DataFrame, right: pd.DataFrame, key: str) -> pd.DataFrame:
    result = left.merge(right, on=key, how="left", validate="many_to_one", indicator=True)
    if len(result) != len(left) or not result["_merge"].eq("both").all():
        raise ValueError("Mandatory analysis relationship failed")
    return result.drop(columns="_merge")


def days(start: pd.Series, end: pd.Series) -> pd.Series:
    valid = start.notna() & end.notna() & end.ge(start)
    return ((end - start).dt.total_seconds() / 86400).where(valid)


def describe(values: pd.Series) -> dict:
    valid = values.dropna()
    return {
        "eligible": len(valid),
        "excluded": len(values) - len(valid),
        "mean": float(valid.mean()) if len(valid) else None,
        "quantiles": {str(q): float(valid.quantile(q)) for q in (0, 0.25, 0.5, 0.75, 0.9, 1)}
        if len(valid)
        else {},
    }


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", double_precision=12))


def review_comparison(orders: pd.DataFrame, reviews: pd.DataFrame, date_rule: bool) -> dict:
    eligible = orders[orders["delivery_days"].notna()]
    sample = reviews.merge(
        eligible[["order_id", "late_date", "late_timestamp"]],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    sample["late"] = sample["late_date" if date_rule else "late_timestamp"]
    sample["low"] = sample["review_score"].le(2)
    counts = sample.groupby("order_id").size()
    result = {}
    for label, population in (
        ("all_pairs", sample),
        ("single_review_orders", sample[sample["order_id"].map(counts).eq(1)]),
    ):
        groups = []
        for late, group in population.groupby("late", sort=True):
            low = int(group["low"].sum())
            groups.append(
                {
                    "late": bool(late),
                    "reviews": len(group),
                    "low": low,
                    "low_rate": ratio(low, len(group)),
                    "wilson95": wilson(low, len(group)),
                    "mean_score": float(group["review_score"].mean()),
                }
            )
        result[label] = groups
    return result


def analyze(t: dict[str, pd.DataFrame]) -> dict:
    """Preserve source grains and exact cents; no identifiers enter returned evidence."""
    for name, contract in TABLES.items():
        if contract.key and t[name].duplicated(list(contract.key)).any():
            raise ValueError("Source grain failed")
    orders = t["orders"].copy()
    for column in TABLES["orders"].columns:
        if column.endswith(("timestamp", "date")) or column == "order_approved_at":
            orders[column] = pd.to_datetime(orders[column], format="%Y-%m-%d %H:%M:%S")
    orders = join(orders, t["customers"], "customer_id")
    items, payments = t["order_items"].copy(), t["order_payments"].copy()
    reviews = t["order_reviews"][["order_id", "review_id", "review_score"]].copy()
    reviews["review_score"] = reviews["review_score"].astype(int)
    for child in (items, payments, reviews):
        if not child["order_id"].isin(orders["order_id"]).all():
            raise ValueError("Child order membership failed")
    for frame, columns in ((items, ("price", "freight_value")), (payments, ("payment_value",))):
        for column in columns:
            frame[column + "_cents"] = frame[column].map(cents)
    payments["payment_installments"] = payments["payment_installments"].astype(int)
    ia = items.groupby("order_id").agg(
        items=("order_item_id", "size"),
        price_cents=("price_cents", "sum"),
        freight_cents=("freight_value_cents", "sum"),
    )
    pa = payments.groupby("order_id").agg(
        payments=("payment_sequential", "size"), payment_cents=("payment_value_cents", "sum")
    )
    ra = reviews.groupby("order_id").agg(reviews=("review_id", "size"))
    for aggregate in (ia, pa, ra):
        aggregate = aggregate.astype("Int64")
        orders = orders.merge(
            aggregate, left_on="order_id", right_index=True, how="left", validate="one_to_one"
        )
    for column in ("items", "payments", "reviews"):
        orders[column] = orders[column].fillna(0)
    if orders["order_id"].duplicated().any():
        raise ValueError("Order grain failed")
    for column, frame, source_column in (
        ("price_cents", items, "price_cents"),
        ("freight_cents", items, "freight_value_cents"),
        ("payment_cents", payments, "payment_value_cents"),
    ):
        if int(orders[column].sum()) != int(frame[source_column].sum()):
            raise ValueError("Exact amount conservation failed")
    orders["month"] = orders["order_purchase_timestamp"].dt.strftime("%Y-%m")
    delivered = orders["order_status"].eq("delivered")
    orders["delivery_days"] = days(
        orders["order_purchase_timestamp"], orders["order_delivered_customer_date"]
    ).where(delivered)
    orders["handling_days"] = days(
        orders["order_approved_at"], orders["order_delivered_carrier_date"]
    ).where(delivered)
    orders["transit_days"] = days(
        orders["order_delivered_carrier_date"], orders["order_delivered_customer_date"]
    ).where(delivered)
    actual, estimate = (
        orders["order_delivered_customer_date"],
        orders["order_estimated_delivery_date"],
    )
    orders["late_timestamp"] = actual.gt(estimate).where(orders["delivery_days"].notna())
    orders["late_date"] = (
        actual.dt.normalize().gt(estimate.dt.normalize()).where(orders["delivery_days"].notna())
    )
    monthly = orders.groupby("month").agg(
        orders=("order_id", "size"),
        price_cents=("price_cents", lambda s: s.sum(min_count=1)),
        payment_cents=("payment_cents", lambda s: s.sum(min_count=1)),
        delivered_orders=("order_status", lambda s: int(s.eq("delivered").sum())),
    )
    statuses = orders.groupby("order_status").agg(
        orders=("order_id", "size"),
        price_cents=("price_cents", lambda s: s.sum(min_count=1)),
        missing_items=("items", lambda s: int(s.eq(0).sum())),
        missing_payments=("payments", lambda s: int(s.eq(0).sum())),
        missing_reviews=("reviews", lambda s: int(s.eq(0).sum())),
    )
    products = t["products"].merge(
        t["category_translation"], on="product_category_name", how="left", validate="many_to_one"
    )
    enriched = join(join(items, products, "product_id"), t["sellers"], "seller_id")
    enriched = join(
        enriched,
        orders[["order_id", "order_status", "customer_state", "delivery_days", "late_date"]],
        "order_id",
    )
    enriched["category"] = enriched["product_category_name"].replace("", "[missing category]")
    category = enriched.groupby("category").agg(
        items=("order_item_id", "size"),
        orders=("order_id", "nunique"),
        price_cents=("price_cents", "sum"),
        freight_cents=("freight_value_cents", "sum"),
        delivered_price_cents=(
            "price_cents",
            lambda s: int(s[enriched.loc[s.index, "order_status"].eq("delivered")].sum()),
        ),
    )
    category = category.sort_values(["price_cents", "category"], ascending=[False, True])
    category_order = enriched.drop_duplicates(["category", "order_id"])
    operations = category_order.groupby("category").agg(
        eligible=("delivery_days", "count"),
        late=("late_date", lambda s: int(s.fillna(False).sum())),
        median_days=("delivery_days", "median"),
    )
    category = category.join(operations, validate="one_to_one")
    product_totals = items.groupby("product_id")["price_cents"].sum().sort_values(ascending=False)
    seller_totals = items.groupby("seller_id")["price_cents"].sum().sort_values(ascending=False)
    seller_order = enriched.drop_duplicates(["seller_id", "order_id"])
    support = seller_order.groupby("seller_id").agg(
        orders=("order_id", "size"),
        eligible=("delivery_days", "count"),
        late=("late_date", lambda s: int(s.fillna(False).sum())),
    )
    supported = support[support["eligible"].ge(100)].copy()
    supported["late_rate"] = supported["late"] / supported["eligible"]
    state = orders.groupby("customer_state").agg(
        orders=("order_id", "size"),
        price_cents=("price_cents", lambda s: s.sum(min_count=1)),
        eligible=("delivery_days", "count"),
        median_days=("delivery_days", "median"),
        late=("late_date", lambda s: int(s.fillna(False).sum())),
    )
    state = state.sort_values(["orders", "customer_state"], ascending=[False, True])
    enriched["cross_state"] = enriched["seller_state"].ne(enriched["customer_state"])
    route = enriched.groupby("order_id")["cross_state"].any().rename("any_cross_state")
    routes = orders.merge(
        route, left_on="order_id", right_index=True, how="inner", validate="one_to_one"
    )
    route_results = []
    for cross, group in routes.groupby("any_cross_state"):
        valid = group[group["delivery_days"].notna()]
        route_results.append(
            {
                "any_cross_state": bool(cross),
                "orders": len(group),
                "eligible": len(valid),
                "duration": describe(valid["delivery_days"]),
                "late": int(valid["late_date"].sum()),
                "late_rate": ratio(int(valid["late_date"].sum()), len(valid)),
            }
        )
    zip_summary = (
        t["geolocation"]
        .groupby("geolocation_zip_code_prefix")
        .agg(cities=("geolocation_city", "nunique"), states=("geolocation_state", "nunique"))
    )
    methods = payments.groupby("payment_type").agg(
        components=("order_id", "size"),
        orders=("order_id", "nunique"),
        value_cents=("payment_value_cents", "sum"),
        median_installments=("payment_installments", "median"),
    )
    identity = orders.groupby("customer_unique_id").size()
    identity_delivered = orders[delivered].groupby("customer_unique_id").size()
    comparable = orders[orders["price_cents"].notna() & orders["payment_cents"].notna()]
    difference = (
        comparable["payment_cents"] - comparable["price_cents"] - comparable["freight_cents"]
    )
    freight_ratio = orders["freight_cents"] / orders["price_cents"].where(
        orders["price_cents"].gt(0)
    )
    eligible = orders[orders["delivery_days"].notna()]
    return {
        "population": {
            "orders": len(orders),
            "items": len(items),
            "payments": len(payments),
            "review_pairs": len(reviews),
            "identities": len(identity),
            "purchase_min": str(orders["order_purchase_timestamp"].min()),
            "purchase_max": str(orders["order_purchase_timestamp"].max()),
            **{
                "missing_" + c: int(orders[c].eq(0).sum()) for c in ("items", "payments", "reviews")
            },
            "multi_review_orders": int(orders["reviews"].gt(1).sum()),
        },
        "sales": {
            "price_cents": int(items["price_cents"].sum()),
            "freight_cents": int(items["freight_value_cents"].sum()),
            "payment_cents": int(payments["payment_value_cents"].sum()),
            "monthly": records(monthly.reset_index()),
            "statuses": records(statuses.reset_index()),
            "item_price_cents": describe(items["price_cents"]),
            "order_price_cents": describe(orders["price_cents"]),
            "order_freight_to_price": describe(freight_ratio),
        },
        "products": {
            "categories": records(category.reset_index()),
            "top10_product_value_share": ratio(
                int(product_totals.head(10).sum()), int(product_totals.sum())
            ),
            "top100_product_value_share": ratio(
                int(product_totals.head(100).sum()), int(product_totals.sum())
            ),
            "missing_category_products": int(products["product_category_name"].eq("").sum()),
            "untranslated_products": int(
                (
                    products["product_category_name"].ne("")
                    & products["product_category_name_english"].isna()
                ).sum()
            ),
        },
        "customers": {
            "all_status_identities": len(identity),
            "repeat_identities": int(identity.gt(1).sum()),
            "repeat_identity_rate": ratio(int(identity.gt(1).sum()), len(identity)),
            "delivered_identities": len(identity_delivered),
            "repeat_delivered_identities": int(identity_delivered.gt(1).sum()),
            "repeat_delivered_rate": ratio(
                int(identity_delivered.gt(1).sum()), len(identity_delivered)
            ),
            "orders_per_identity": describe(identity),
        },
        "sellers": {
            "sellers": len(seller_totals),
            "top10_value_share": ratio(int(seller_totals.head(10).sum()), int(seller_totals.sum())),
            "top100_value_share": ratio(
                int(seller_totals.head(100).sum()), int(seller_totals.sum())
            ),
            "eligible_order_support_threshold": 100,
            "supported_sellers": len(supported),
            "supported_late_rate": describe(supported["late_rate"]),
            "seller_order_associations": len(seller_order),
        },
        "geography": {
            "customer_states": records(state.reset_index()),
            "routes": route_results,
            "zip_prefixes": len(zip_summary),
            "city_ambiguous_zips": int(zip_summary["cities"].gt(1).sum()),
            "state_ambiguous_zips": int(zip_summary["states"].gt(1).sum()),
            "customer_rows_without_geo": int(
                (~t["customers"]["customer_zip_code_prefix"].isin(zip_summary.index)).sum()
            ),
            "seller_rows_without_geo": int(
                (~t["sellers"]["seller_zip_code_prefix"].isin(zip_summary.index)).sum()
            ),
        },
        "payments": {
            "methods": records(methods.reset_index()),
            "installments": records(
                payments.groupby("payment_installments")
                .agg(components=("order_id", "size"), value_cents=("payment_value_cents", "sum"))
                .reset_index()
            ),
            "multiple_component_orders": int(orders["payments"].gt(1).sum()),
            "zero_value_components": int(payments["payment_value_cents"].eq(0).sum()),
            "zero_installment_components": int(payments["payment_installments"].eq(0).sum()),
            "comparable_orders": len(comparable),
            "exact_match_orders": int(difference.eq(0).sum()),
            "payment_minus_items_freight_cents": int(difference.sum()),
            "absolute_difference_cents": int(difference.abs().sum()),
        },
        "logistics": {
            "delivered_status_orders": int(delivered.sum()),
            "eligible_delivery_orders": len(eligible),
            "excluded_delivered_orders": int(delivered.sum()) - len(eligible),
            **{
                c: describe(orders.loc[delivered, c])
                for c in ("delivery_days", "handling_days", "transit_days")
            },
            "late_timestamp": int(eligible["late_timestamp"].sum()),
            "late_date": int(eligible["late_date"].sum()),
            "monthly": records(
                eligible.groupby("month")
                .agg(
                    eligible=("order_id", "size"),
                    late=("late_date", lambda s: int(s.sum())),
                    median_days=("delivery_days", "median"),
                )
                .reset_index()
            ),
        },
        "reviews": {
            "score_distribution": {
                str(k): int(v)
                for k, v in reviews["review_score"].value_counts().sort_index().items()
            },
            "mean_pair_score": float(reviews["review_score"].mean()),
            "timestamp_lateness": review_comparison(orders, reviews, False),
            "calendar_lateness": review_comparison(orders, reviews, True),
        },
    }


def run(root: Path, output: Path) -> Path:
    plan = prepare_source(root)
    tables = {
        name: pd.DataFrame(iter_source_rows(root, name), columns=list(contract.columns))
        for name, contract in TABLES.items()
    }
    result = analyze(tables)
    if prepare_source(root) != plan:
        raise ValueError("Source changed during analysis")
    result["provenance"] = {
        "source_fingerprint": plan.fingerprint,
        "manifest_sha256": plan.manifest_sha256,
        "eligibility_version": "phase4-exploratory-v1",
        "table_rows": {name: evidence.rows for name, evidence in plan.tables.items()},
        "money_representation": "integer BRL cents from strict decimal text",
        "database_operations": 0,
    }
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    directory = output / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "results.json").write_text(encoded, encoding="utf-8")
    (directory / "receipt.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "results_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                "source_unchanged": True,
                "aggregate_only": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        path = run(args.root, args.output or args.root / ".artifacts/phase-4")
    except Exception:
        print(
            "Phase 4 analysis failed; inspect contracts and retained evidence. Details suppressed."
        )
        return 1
    print(f"Phase 4 aggregate evidence retained: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
