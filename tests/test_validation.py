"""Small source datasets exercise preservation, quality gates, and staged outputs."""

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from src.cleaning.staging import read_source, standardize
from src.ingestion.olist import acquire, sha256_file
from src.validation.contracts import TABLES
from src.validation.profile import (
    contextual_checks,
    relationship_checks,
    table_profile,
    validate_frame,
)
from src.validation.run import report_markdown, run


@pytest.fixture
def source_rows():
    customer, order, product, seller = (character * 32 for character in "1234")
    return {
        "customers": [
            {
                "customer_id": customer,
                "customer_unique_id": "a" * 32,
                "customer_zip_code_prefix": "00123",
                "customer_city": "sao paulo",
                "customer_state": "SP",
            }
        ],
        "geolocation": [
            {
                "geolocation_zip_code_prefix": "00123",
                "geolocation_lat": "-23.5505",
                "geolocation_lng": "-46.6333",
                "geolocation_city": "sao paulo",
                "geolocation_state": "SP",
            },
            {
                "geolocation_zip_code_prefix": "00123",
                "geolocation_lat": "-23.5510",
                "geolocation_lng": "-46.6340",
                "geolocation_city": "são paulo",
                "geolocation_state": "SP",
            },
        ],
        "orders": [
            {
                "order_id": order,
                "customer_id": customer,
                "order_status": "delivered",
                "order_purchase_timestamp": "2018-01-01 10:00:00",
                "order_approved_at": "2018-01-01 11:00:00",
                "order_delivered_carrier_date": "2018-01-02 12:00:00",
                "order_delivered_customer_date": "2018-01-05 13:00:00",
                "order_estimated_delivery_date": "2018-01-10 00:00:00",
            }
        ],
        "order_items": [
            {
                "order_id": order,
                "order_item_id": "1",
                "product_id": product,
                "seller_id": seller,
                "shipping_limit_date": "2018-01-03 00:00:00",
                "price": "100.00",
                "freight_value": "25.00",
            }
        ],
        "order_payments": [
            {
                "order_id": order,
                "payment_sequential": "1",
                "payment_type": "credit_card",
                "payment_installments": "1",
                "payment_value": "125.00",
            }
        ],
        "order_reviews": [
            {
                "review_id": "5" * 32,
                "order_id": order,
                "review_score": "5",
                "review_comment_title": "NA",
                "review_comment_message": 'First line\nSecond line, with "quotes" and café',
                "review_creation_date": "2018-01-06 00:00:00",
                "review_answer_timestamp": "2018-01-07 10:00:00",
            },
            {
                "review_id": "6" * 32,
                "order_id": order,
                "review_score": "4",
                "review_comment_title": "",
                "review_comment_message": "",
                "review_creation_date": "2018-01-06 00:00:00",
                "review_answer_timestamp": "2018-01-07 11:00:00",
            },
        ],
        "products": [
            {
                "product_id": product,
                "product_category_name": "cama_mesa_banho",
                "product_name_lenght": "12",
                "product_description_lenght": "80",
                "product_photos_qty": "2",
                "product_weight_g": "300.00",
                "product_length_cm": "20.00",
                "product_height_cm": "10.00",
                "product_width_cm": "15.00",
            }
        ],
        "sellers": [
            {
                "seller_id": seller,
                "seller_zip_code_prefix": "00123",
                "seller_city": "sao paulo",
                "seller_state": "SP",
            }
        ],
        "category_translation": [
            {
                "product_category_name": "cama_mesa_banho",
                "product_category_name_english": "bed_bath_table",
            }
        ],
    }


def write_sources(directory: Path, rows: dict) -> None:
    directory.mkdir()
    for table, spec in TABLES.items():
        with (directory / spec.filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(spec.columns))
            writer.writeheader()
            writer.writerows(rows[table])


@pytest.fixture
def validation_paths(tmp_path, source_rows):
    project, source = tmp_path / "project", tmp_path / "source"
    project.mkdir()
    write_sources(source, source_rows)
    return project, source


def frames_from_source(source: Path) -> dict[str, pd.DataFrame]:
    return {
        table: standardize(read_source(source / spec.filename, table), table)[0]
        for table, spec in TABLES.items()
    }


def positive_errors(checks: list[dict]) -> list[dict]:
    return [check for check in checks if check["severity"] == "error" and check["count"] > 0]


def assert_check_contract(checks: list[dict]) -> None:
    assert checks
    for check in checks:
        assert {"name", "table", "severity", "count", "unit"} <= check.keys()
        assert check["severity"] in {"error", "warning", "info"}
        assert type(check["count"]) is int
        assert check["count"] >= 0


def test_standardization_preserves_zip_text_multiline_and_optional_nulls(
    validation_paths,
):
    _, source = validation_paths
    frames = frames_from_source(source)
    for table, column in (
        ("customers", "customer_zip_code_prefix"),
        ("sellers", "seller_zip_code_prefix"),
        ("geolocation", "geolocation_zip_code_prefix"),
    ):
        assert frames[table][column].iloc[0] == "00123"
        assert str(frames[table][column].dtype).startswith("string")
    reviews = frames["order_reviews"]
    assert reviews.loc[0, "review_comment_title"] == "NA"
    assert reviews.loc[0, "review_comment_message"] == (
        'First line\nSecond line, with "quotes" and café'
    )
    assert pd.isna(reviews.loc[1, "review_comment_title"])
    assert pd.isna(reviews.loc[1, "review_comment_message"])
    assert reviews["_source_row"].tolist() == [1, 2]
    checks = validate_frame("order_reviews", reviews)
    assert_check_contract(checks)
    assert not positive_errors(checks)


def test_invalid_numbers_and_dates_are_counted_without_dropping_rows(validation_paths):
    _, source = validation_paths
    raw = read_source(source / TABLES["order_items"].filename, "order_items")
    raw.loc[0, "price"] = "not-a-number"
    raw.loc[0, "order_item_id"] = "1.5"
    raw.loc[0, "shipping_limit_date"] = "not-a-date"
    frame, failures = standardize(raw, "order_items")
    assert failures["price"] == 1
    assert failures["order_item_id"] == 1
    assert failures["shipping_limit_date"] == 1
    assert len(frame) == len(raw) == 1
    assert frame["_source_row"].tolist() == [1]
    for column in ("price", "order_item_id", "shipping_limit_date"):
        assert pd.isna(frame.loc[0, column])


@pytest.mark.parametrize("problem", ["wrong-header", "empty"])
def test_reader_rejects_schema_changes_and_empty_tables(validation_paths, problem):
    _, source = validation_paths
    table = "customers"
    path = source / TABLES[table].filename
    if problem == "wrong-header":
        path.write_text(path.read_text().replace("customer_id", "unexpected_id", 1))
    else:
        path.write_text(",".join(TABLES[table].columns) + "\n")
    with pytest.raises(ValueError):
        read_source(path, table)


def test_confirmed_key_duplicates_fail_but_geography_repeated_zip_is_retained(
    validation_paths,
):
    _, source = validation_paths
    frames = frames_from_source(source)
    geography = frames["geolocation"]
    assert len(geography) == 2
    assert geography["geolocation_zip_code_prefix"].nunique() == 1
    geography_checks = validate_frame("geolocation", geography)
    assert_check_contract(geography_checks)
    assert not positive_errors(geography_checks)
    duplicate_customers = pd.concat([frames["customers"], frames["customers"]], ignore_index=True)
    checks = validate_frame("customers", duplicate_customers)
    assert_check_contract(checks)
    assert positive_errors(checks)
    assert len(duplicate_customers) == 2


def test_confirmed_relationship_orphan_is_an_error(validation_paths):
    _, source = validation_paths
    frames = frames_from_source(source)
    baseline = relationship_checks(frames)
    assert_check_contract(baseline)
    assert not positive_errors(baseline)
    frames["orders"].loc[0, "customer_id"] = "f" * 32
    checks = relationship_checks(frames)
    assert_check_contract(checks)
    assert any(check["count"] == 1 for check in positive_errors(checks))


def test_successful_run_roundtrips_all_rows_and_is_reproducible(validation_paths, source_rows):
    project, source = validation_paths
    manifest = acquire(project, source)
    result = run(project)
    assert result["status"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert not positive_errors(result["checks"])
    assert result["staging"]["promoted"] is True
    relative_staging = Path(result["staging"]["path"])
    assert not relative_staging.is_absolute()
    staging = project / relative_staging
    assert staging.resolve().is_relative_to(project.resolve())
    expected_frames = frames_from_source(source)
    assert {path.name for path in staging.glob("*.parquet")} == {
        f"{table}.parquet" for table in TABLES
    }
    first_hashes = {}
    for table in TABLES:
        path = staging / f"{table}.parquet"
        restored = pd.read_parquet(path)
        assert len(restored) == len(source_rows[table])
        pd.testing.assert_frame_equal(restored, expected_frames[table])
        first_hashes[table] = sha256_file(path)
    report_json = project / "docs" / "data-quality-report.json"
    saved_report = json.loads(report_json.read_text(encoding="utf-8"))
    assert saved_report["status"] == result["status"]
    assert saved_report["checks"] == result["checks"]
    assert (project / "docs" / "data-quality-report.md").stat().st_size > 0
    assert (project / "docs" / "data_dictionary" / "initial.md").stat().st_size > 0
    repeated = run(project)
    assert repeated["status"] == result["status"]
    assert {table: sha256_file(staging / f"{table}.parquet") for table in TABLES} == first_hashes
    for name, record in manifest["files"].items():
        assert sha256_file(project / "data" / "raw" / "olist-v2" / name) == record["sha256"]


@pytest.mark.parametrize("invalid_source", ["schema", "duplicate-key", "parse-failure"])
def test_invalid_source_blocks_promotion_and_preserves_existing_staging(
    validation_paths, invalid_source
):
    project, source = validation_paths
    if invalid_source == "schema":
        path = source / TABLES["customers"].filename
        path.write_text(path.read_text().replace("customer_id", "unexpected_id", 1))
    elif invalid_source == "duplicate-key":
        path = source / TABLES["customers"].filename
        with path.open("r", newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        with path.open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(rows[1])
    else:
        path = source / TABLES["order_items"].filename
        path.write_text(path.read_text().replace("100.00", "bad-number", 1))
    manifest = acquire(project, source)
    existing = project / "data" / "interim" / "olist-v2-v1"
    existing.mkdir(parents=True)
    marker = existing / "previous-staging.parquet"
    marker.write_bytes(b"previous staging remains unchanged")
    before = marker.read_bytes()
    result = run(project)
    assert result["status"] == "FAIL"
    assert positive_errors(result["checks"])
    assert result["staging"]["promoted"] is False
    assert marker.read_bytes() == before
    assert list(existing.iterdir()) == [marker]
    for name, record in manifest["files"].items():
        assert sha256_file(project / "data" / "raw" / "olist-v2" / name) == record["sha256"]


def test_raw_hash_tamper_fails_without_creating_staging(validation_paths):
    project, source = validation_paths
    acquire(project, source)
    raw = project / "data" / "raw" / "olist-v2" / TABLES["customers"].filename
    modified = raw.read_bytes() + b"\n"
    raw.write_bytes(modified)
    result = run(project)
    assert result["status"] == "FAIL"
    assert positive_errors(result["checks"])
    assert result["staging"]["promoted"] is False
    assert not (project / "data" / "interim" / "olist-v2-v1").exists()
    assert raw.read_bytes() == modified


def test_lifecycle_reversal_detected_when_intermediate_events_are_missing(validation_paths):
    _, source = validation_paths
    frames = frames_from_source(source)
    orders = frames["orders"]
    orders.loc[0, "order_approved_at"] = pd.NaT
    orders.loc[0, "order_delivered_carrier_date"] = pd.NaT
    orders.loc[0, "order_delivered_customer_date"] = pd.Timestamp("2017-12-31 12:00:00")
    checks, status_profile = contextual_checks(frames)
    reversal = next(
        check
        for check in checks
        if check["name"] == "sequence:order_delivered_customer_date_before_order_purchase_timestamp"
    )
    assert reversal["count"] == 1
    assert reversal["severity"] == "warning"
    assert status_profile["delivered"]["missing_events"]["order_approved_at"] == 1
    assert status_profile["delivered"]["missing_events"]["order_delivered_carrier_date"] == 1
    assert len(orders) == 1
    assert orders.loc[0, "order_delivered_customer_date"] == pd.Timestamp("2017-12-31 12:00:00")


def review_report(raw: pd.DataFrame | None = None) -> dict:
    report = {
        "status": "FAIL",
        "generated_at_utc": "2026-09-19T00:00:00+00:00",
        "error_checks": 1,
        "warning_checks": 0,
        "tables": {},
        "checks": [],
        "staging": {"promoted": False, "path": None},
    }
    if raw is not None:
        frame, _ = standardize(raw, "order_reviews")
        report["tables"]["order_reviews"] = table_profile("order_reviews", raw, frame, {})
        report["checks"] = validate_frame("order_reviews", frame)
        report["error_checks"] = len(positive_errors(report["checks"]))
        report["status"] = "FAIL" if report["error_checks"] else "PASS"
    return report


def test_markdown_reports_review_key_validation_unavailable_when_reviews_are_absent():
    rendered = report_markdown(review_report())
    assert "Review key validation is unavailable" in rendered
    assert "uniqueness/null checks passed" not in rendered


@pytest.mark.parametrize("problem", ["duplicate-composite-key", "null-composite-key"])
def test_markdown_reports_failed_review_key_validation(validation_paths, problem):
    _, source = validation_paths
    raw = read_source(source / TABLES["order_reviews"].filename, "order_reviews")
    if problem == "duplicate-composite-key":
        raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    else:
        raw.loc[0, "review_id"] = ""
    report = review_report(raw)
    assert report["status"] == "FAIL"
    rendered = report_markdown(report)
    assert "(review_id, order_id) uniqueness/null checks failed" in rendered
    assert "uniqueness/null checks passed" not in rendered


def test_markdown_reports_actual_individual_review_key_counts_for_unique_snapshot(validation_paths):
    _, source = validation_paths
    raw = read_source(source / TABLES["order_reviews"].filename, "order_reviews").iloc[[0]]
    report = review_report(raw)
    assert report["status"] == "PASS"
    rendered = report_markdown(report)
    assert "(review_id, order_id) uniqueness/null checks passed" in rendered
    assert "review_id: 0 rows in repeated keys" in rendered
    assert "order_id: 0 rows in repeated keys" in rendered


def test_reader_accepts_utf8_bom_without_changing_source_bytes(validation_paths):
    _, source = validation_paths
    path = source / TABLES["customers"].filename
    original_frame = read_source(path, "customers")
    with_bom = b"\xef\xbb\xbf" + path.read_bytes()
    path.write_bytes(with_bom)
    loaded = read_source(path, "customers")
    pd.testing.assert_frame_equal(loaded, original_frame)
    assert loaded.loc[0, "customer_zip_code_prefix"] == "00123"
    assert path.read_bytes() == with_bom


@pytest.mark.parametrize("problem", ["too-few-fields", "too-many-fields", "blank-record"])
def test_reader_rejects_malformed_field_counts_instead_of_dropping_records(
    validation_paths, problem
):
    _, source = validation_paths
    path = source / TABLES["customers"].filename
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    malformed = {
        "too-few-fields": rows[1][:-1],
        "too-many-fields": [*rows[1], "extra-field"],
        "blank-record": [],
    }[problem]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows([*rows, malformed, rows[1]])
    before = path.read_bytes()
    with pytest.raises(ValueError, match="wrong field count"):
        read_source(path, "customers")
    assert path.read_bytes() == before
