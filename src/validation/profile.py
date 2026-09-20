"""Observable quality checks; no deduplication, KPI calculation, or business inference."""

import math
import warnings
from itertools import combinations

import pandas as pd
import pandera.pandas as pa

from src.validation.contracts import INTEGER, RELATIONSHIPS, TABLES, D, F

STATUSES = {
    "created",
    "approved",
    "invoiced",
    "processing",
    "shipped",
    "delivered",
    "unavailable",
    "canceled",
}
PAYMENT_TYPES = {"credit_card", "boleto", "voucher", "debit_card", "not_defined"}
STATES = set(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)


def _percentile(series: pd.Series, fraction: float) -> float | None:
    if series.empty:
        return None
    # Bad finite source values can overflow interpolation before schema checks report them.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = float(series.quantile(fraction))
    return result if math.isfinite(result) else None


def check(name, table, severity, count, detail, unit="rows"):
    return {
        "name": name,
        "table": table,
        "severity": severity,
        "count": int(count),
        "unit": unit,
        "detail": detail,
    }


def validate_frame(table: str, frame: pd.DataFrame) -> list[dict]:
    spec = TABLES[table]
    columns = {}
    for name, column in spec.columns.items():
        rules = []
        if column.dtype == "string" and name.endswith("_id"):
            rules.append(pa.Check.str_matches(r"^[0-9a-f]{32}$"))
        if name.endswith("zip_code_prefix"):
            rules.append(pa.Check.str_matches(r"^[0-9]{1,5}$"))
        if name.endswith("_state"):
            rules.append(pa.Check.isin(STATES))
        if column.dtype in (INTEGER, F) and name not in {
            "geolocation_lat",
            "geolocation_lng",
        }:
            rules.append(pa.Check.ge(0))
        if name in {"order_item_id", "payment_sequential"}:
            rules.append(pa.Check.ge(1))
        if name == "review_score":
            rules.append(pa.Check.in_range(1, 5))
        if name == "order_status":
            rules.append(pa.Check.isin(STATUSES))
        if name == "payment_type":
            rules.append(pa.Check.isin(PAYMENT_TYPES))
        if name == "geolocation_lat":
            rules.append(pa.Check.in_range(-90, 90))
        if name == "geolocation_lng":
            rules.append(pa.Check.in_range(-180, 180))
        columns[name] = pa.Column(column.dtype, checks=rules, nullable=column.nullable)
    columns["_source_row"] = pa.Column(INTEGER, pa.Check.ge(1), unique=True)
    schema = pa.DataFrameSchema(columns, strict=True, unique=list(spec.key) or None, coerce=False)
    issues = []
    try:
        schema.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        # Aggregate rule counts only; never publish raw review text or row-level records.
        failures = exc.failure_cases
        for (column, rule), group in failures.groupby(["column", "check"], dropna=False):
            issues.append({"column": str(column), "rule": str(rule), "failure_count": len(group)})
    result = check(
        "schema",
        table,
        "error",
        len(issues),
        "Pandera types, nullability, domains, and confirmed keys.",
        "rules",
    )
    result["failed_rules"] = issues
    return [result]


def table_profile(table: str, raw: pd.DataFrame, frame: pd.DataFrame, source_record: dict) -> dict:
    spec = TABLES[table]
    columns = {}
    for name, column in spec.columns.items():
        series = frame[name]
        nonnull = series.dropna()
        value = {
            "dtype": str(series.dtype),
            "nullable_by_contract": column.nullable,
            "nulls": int(series.isna().sum()),
            "distinct_non_null": int(series.nunique()),
            "description": column.description,
        }
        if column.dtype in (INTEGER, F, D):
            value["min"] = str(nonnull.min()) if len(nonnull) else None
            value["max"] = str(nonnull.max()) if len(nonnull) else None
        if column.dtype in (INTEGER, F):
            value["zero_count"] = int(series.eq(0).sum())
            value["negative_count"] = int(series.lt(0).sum())
            value["p01"] = _percentile(nonnull, 0.01)
            value["p99"] = _percentile(nonnull, 0.99)
            if len(nonnull) and (value["p01"] is None or value["p99"] is None):
                value["statistics_note"] = (
                    "A percentile is unavailable because source values exceed finite "
                    "interpolation precision; inspect the validation checks."
                )
        if name in {"order_status", "payment_type"} or name.endswith("_state"):
            domain = (
                STATUSES
                if name == "order_status"
                else PAYMENT_TYPES
                if name == "payment_type"
                else STATES
            )
            value["values"] = {
                str(k): int(v) for k, v in series[series.isin(domain)].value_counts().items()
            }
            value["unknown_value_count"] = int((series.notna() & ~series.isin(domain)).sum())
        if column.dtype == "string":
            value["max_length"] = int(series.str.len().max()) if len(nonnull) else 0
        columns[name] = value
    key_checks = {}
    for key in ((spec.key,) if spec.key else ()) + spec.candidates:
        key_checks[", ".join(key)] = {
            "distinct_keys": len(frame[list(key)].drop_duplicates()),
            "rows_in_duplicate_keys": int(frame.duplicated(list(key), keep=False).sum()),
            "null_key_rows": int(frame[list(key)].isna().any(axis=1).sum()),
            "enforced": key == spec.key,
        }
    return {
        "filename": spec.filename,
        **source_record,
        "rows": len(raw),
        "staging_rows": len(frame),
        "source_columns": len(raw.columns),
        "grain": spec.grain,
        "confirmed_key": list(spec.key),
        "duplicate_rows_excluding_first": int(raw.duplicated().sum()),
        "keys": key_checks,
        "columns": columns,
    }


def relationship_checks(frames: dict[str, pd.DataFrame]) -> list[dict]:
    results = []
    for child, column, parent, target, severity in RELATIONSHIPS:
        if child not in frames or parent not in frames:
            continue
        values = frames[child][column]
        missing = values.notna() & ~values.isin(frames[parent][target].dropna())
        results.append(
            check(
                f"reference:{column}->{parent}.{target}",
                child,
                severity,
                missing.sum(),
                "Non-null child values without a parent match; parent uniqueness is separate.",
            )
        )
    return results


def contextual_checks(frames: dict[str, pd.DataFrame]) -> tuple[list[dict], dict]:
    results = []
    orders = frames["orders"]
    status_profile = {}
    events = (
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
    )
    statuses = orders["order_status"].where(
        orders["order_status"].isin(STATUSES), "unknown_or_missing"
    )
    for status, group in orders.groupby(statuses, dropna=False):
        status_profile[str(status)] = {
            "orders": len(group),
            "missing_events": {c: int(group[c].isna().sum()) for c in events},
        }
    chain = ["order_purchase_timestamp", *events]
    for earlier, later in combinations(chain, 2):
        mask = orders[later].notna() & orders[earlier].notna() & (orders[later] < orders[earlier])
        results.append(
            check(
                f"sequence:{later}_before_{earlier}",
                "orders",
                "warning",
                mask.sum(),
                "Source lifecycle reversal; retained for later eligibility decisions.",
            )
        )
    for event in events:
        mask = orders["order_status"].eq("delivered") & orders[event].isna()
        results.append(
            check(
                f"delivered_missing:{event}",
                "orders",
                "warning",
                mask.sum(),
                "Delivered status without a recorded lifecycle timestamp.",
            )
        )
    for child in ("order_items", "order_payments", "order_reviews"):
        missing = ~orders["order_id"].isin(frames[child]["order_id"])
        result = check(
            f"orders_without:{child}",
            "orders",
            "warning",
            missing.sum(),
            "Missing child records are not orphan references; interpret by status.",
            "orders",
        )
        result["by_status"] = {
            str(k): int(v) for k, v in statuses.loc[missing].value_counts().items()
        }
        results.append(result)
    review_counts = frames["order_reviews"].groupby("order_id").size()
    results.append(
        check(
            "multiple_reviews_per_order",
            "order_reviews",
            "warning",
            (review_counts > 1).sum(),
            "Preserve review/order associations; choosing one review requires a later rule.",
            "orders",
        )
    )
    geo = frames["geolocation"]
    outside = ~geo["geolocation_lat"].between(-34, 6) | ~geo["geolocation_lng"].between(-74, -28)
    results.append(
        check(
            "outside_broad_brazil_bounds",
            "geolocation",
            "warning",
            outside.sum(),
            "Exploratory box: latitude [-34,6], longitude [-74,-28]; not a boundary map.",
        )
    )
    results.append(
        check(
            "duplicate_staging_rows",
            "geolocation",
            "warning",
            geo.drop(columns="_source_row").duplicated().sum(),
            "Rows equal after typing are retained; raw duplicates are inventoried separately.",
        )
    )
    products = frames["products"]
    for name in TABLES["products"].columns:
        if name != "product_id":
            results.append(
                check(
                    f"missing:{name}",
                    "products",
                    "warning",
                    products[name].isna().sum(),
                    "Incomplete source product attributes remain null; no imputation.",
                )
            )
    results.append(
        check(
            "zero_weight",
            "products",
            "warning",
            products["product_weight_g"].eq(0).sum(),
            "Zero weight is not converted to missing or a made-up value.",
        )
    )
    payments = frames["order_payments"]
    for name in ("payment_installments", "payment_value"):
        results.append(
            check(
                f"zero:{name}",
                "order_payments",
                "warning",
                payments[name].eq(0).sum(),
                "Source zero retained; review before analytical use.",
            )
        )
    results.append(
        check(
            "undefined_payment_type",
            "order_payments",
            "warning",
            payments["payment_type"].eq("not_defined").sum(),
            "Source not_defined category is preserved.",
        )
    )
    items = frames["order_items"]
    purchase_by_order = orders.set_index("order_id")["order_purchase_timestamp"]
    # Duplicate order keys already block promotion; avoid ambiguous mapping in a failing report.
    if purchase_by_order.index.is_unique:
        purchase = items["order_id"].map(purchase_by_order)
        # Second resolution also handles extreme valid dates without nanosecond overflow.
        days = (
            items["shipping_limit_date"].dt.as_unit("s") - purchase.dt.as_unit("s")
        ).dt.total_seconds() / 86400
        results.append(
            check(
                "shipping_deadline_before_purchase",
                "order_items",
                "warning",
                (days < 0).sum(),
                "Source shipping deadline precedes purchase; no correction applied.",
            )
        )
        results.append(
            check(
                "shipping_deadline_over_365_days",
                "order_items",
                "warning",
                (days > 365).sum(),
                "Exploratory one-year threshold, not an asserted business deadline rule.",
            )
        )
    reviews = frames["order_reviews"]
    results.append(
        check(
            "answer_before_creation",
            "order_reviews",
            "warning",
            (reviews["review_answer_timestamp"] < reviews["review_creation_date"]).sum(),
            "Source review timestamp reversal; retained.",
        )
    )
    return results, status_profile


def join_diagnostics(frames: dict[str, pd.DataFrame]) -> dict:
    items = frames["order_items"].groupby("order_id").size()
    payments = frames["order_payments"].groupby("order_id").size()
    counts = pd.concat([items.rename("items"), payments.rename("payments")], axis=1).fillna(0)
    return {
        "orders_with_multiple_items_and_payments": int(
            ((counts["items"] > 1) & (counts["payments"] > 1)).sum()
        ),
        "inner_join_rows_items_to_payments_on_order": int(
            (counts["items"] * counts["payments"]).sum()
        ),
        "source_item_rows": len(frames["order_items"]),
        "source_payment_rows": len(frames["order_payments"]),
        "interpretation": (
            "Joining item and payment rows on order_id multiplies rows. "
            "Aggregate each to an explicitly chosen grain in Phase 3 "
            "before combining monetary measures."
        ),
    }
