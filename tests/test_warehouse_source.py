"""Source fidelity, stable identity, exact money, and safely reported failures."""

import csv
import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from src.ingestion.olist import DATASET_HANDLE, LICENSE, SOURCE_URL, AcquisitionError, sha256_file
from src.validation.contracts import TABLES
from src.warehouse import source


def write_table(root: Path, name: str, rows: list[list[str]]) -> None:
    path = root / "data/raw/olist-v2" / TABLES[name].filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(TABLES[name].columns)
        writer.writerows(rows)


def write_manifest(root: Path, acquired: str = "2026-09-01T00:00:00+00:00") -> None:
    directory = root / "data/raw/olist-v2"
    manifest = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "dataset_handle": DATASET_HANDLE,
        "dataset_version": 2,
        "license": LICENSE,
        "acquired_at_utc": acquired,
        "files": {
            contract.filename: {
                "sha256": sha256_file(directory / contract.filename),
                "bytes": (directory / contract.filename).stat().st_size,
            }
            for contract in TABLES.values()
        },
    }
    (root / "data/source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    for name, contract in TABLES.items():
        values = ["sample"] * len(contract.columns)
        for money_column in source.MONEY_COLUMNS.get(name, ()):
            values[tuple(contract.columns).index(money_column)] = "0.10"
        write_table(tmp_path, name, [values])
    write_manifest(tmp_path)
    return tmp_path


def test_text_preserves_empty_multiline_unicode_and_leading_zero(snapshot: Path) -> None:
    values = ["review", "order", "5", "", 'Bom, "ótimo"!\r\nSegunda linha', "", "\\N"]
    write_table(snapshot, "order_reviews", [values, values])
    assert list(source.iter_source_rows(snapshot, "order_reviews")) == [tuple(values)] * 2
    customer = ["id", "identity", "00123", "são paulo", "SP"]
    write_table(snapshot, "customers", [customer])
    assert list(source.iter_source_rows(snapshot, "customers")) == [tuple(customer)]


def test_complete_plan_keeps_duplicates_and_exact_sums(snapshot: Path) -> None:
    first = ["order", "1", "product", "seller", "date", "0.10", "1.02"]
    second = ["order", "2", "product", "seller", "date", "0.20", "0.01"]
    write_table(snapshot, "order_items", [first, second])
    geo = ["00123", "-1.00", "-2.00", "city", "SP"]
    write_table(snapshot, "geolocation", [geo, geo])
    write_manifest(snapshot)
    with localcontext() as context:
        context.prec = 2
        plan = source.prepare_source(snapshot)
    assert set(plan.tables) == set(TABLES)
    assert plan.tables["order_items"].money == {"price": "0.30", "freight_value": "1.03"}
    assert plan.tables["geolocation"].rows == 2
    assert plan.tables["geolocation"].money == {}
    digest = hashlib.sha256()
    source.update_digest(digest, 1, geo)
    source.update_digest(digest, 2, geo)
    assert plan.tables["geolocation"].content_sha256 == digest.hexdigest()


def test_identity_ignores_acquisition_time_but_tracks_content_and_contract(
    snapshot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = source.prepare_source(snapshot)
    write_manifest(snapshot, "2026-09-02T00:00:00+00:00")
    same = source.prepare_source(snapshot)
    assert (same.fingerprint, same.load_id) == (first.fingerprint, first.load_id)
    assert same.manifest_sha256 != first.manifest_sha256
    write_table(snapshot, "category_translation", [["source-category", "different"]])
    write_manifest(snapshot)
    changed = source.prepare_source(snapshot)
    assert changed.fingerprint != first.fingerprint
    assert changed.load_id != first.load_id
    monkeypatch.setattr(source, "LANDING_CONTRACT_VERSION", 2)
    assert source.prepare_source(snapshot).fingerprint != changed.fingerprint


def test_digest_distinguishes_boundaries_ordinals_and_empty_fields() -> None:
    def digest(rows: list[tuple[int, tuple[str, ...]]]) -> str:
        result = hashlib.sha256()
        for ordinal, values in rows:
            source.update_digest(result, ordinal, values)
        return result.hexdigest()

    variants = [
        [(1, ("ab", "c"))],
        [(1, ("a", "bc"))],
        [(2, ("ab", "c"))],
        [(1, ("ab", "c", ""))],
        [(1, ("ab", "c", "\\N"))],
        [(1, ("ab",)), (2, ("c",))],
    ]
    assert len({digest(rows) for rows in variants}) == len(variants)
    with pytest.raises(ValueError, match="positive"):
        source.update_digest(hashlib.sha256(), 0, ("field",))


@pytest.mark.parametrize(
    "value",
    [
        "",
        "NaN",
        "Infinity",
        "-1.00",
        "+1.00",
        "1e2",
        "1.001",
        " 1.00",
        "1.",
        "10000000000000000.00",
        "private-invalid-source-text",
    ],
)
def test_money_rejects_rounding_nonfinite_range_and_unsupported_syntax(value: str) -> None:
    with pytest.raises(source.SourceError) as error:
        source.parse_money(value)
    if value:
        assert value not in str(error.value)


@pytest.mark.parametrize("value", ["0", "0.00", "0001.2", "9999999999999999.99"])
def test_money_accepts_exact_nonnegative_range(value: str) -> None:
    assert source.parse_money(value) == Decimal(value)


@pytest.mark.parametrize("kind", ["header", "width", "nul", "invalid_csv", "invalid_utf8"])
def test_source_errors_do_not_echo_values(snapshot: Path, kind: str) -> None:
    path = snapshot / "data/raw/olist-v2" / TABLES["category_translation"].filename
    private = "private-source-text"
    if kind == "header":
        path.write_text(private + "\nvalue\n", encoding="utf-8")
    elif kind == "width":
        write_table(snapshot, "category_translation", [[private]])
    elif kind == "nul":
        write_table(snapshot, "category_translation", [[private + "\x00", "value"]])
    else:
        header = ",".join(TABLES["category_translation"].columns).encode() + b"\n"
        path.write_bytes(header + (b'"' + private.encode() if kind == "invalid_csv" else b"\xff"))
    with pytest.raises(source.SourceError) as error:
        list(source.iter_source_rows(snapshot, "category_translation"))
    assert private not in str(error.value)


def test_raw_integrity_failure_propagates(snapshot: Path) -> None:
    write_table(snapshot, "category_translation", [["changed", "data"]])
    with pytest.raises(AcquisitionError, match="integrity mismatch"):
        source.prepare_source(snapshot)


def test_changed_manifest_during_preparation_is_rejected(
    snapshot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_verify = source.verify_raw
    calls = 0

    def mutate_before_final_verification(root: Path) -> dict:
        nonlocal calls
        calls += 1
        if calls == 2:
            write_manifest(root, "2026-09-03T00:00:00+00:00")
        return original_verify(root)

    monkeypatch.setattr(source, "verify_raw", mutate_before_final_verification)
    with pytest.raises(source.SourceError, match="provenance changed"):
        source.prepare_source(snapshot)
    assert calls == 2


def test_empty_source_table_is_not_a_successful_snapshot(snapshot: Path) -> None:
    write_table(snapshot, "category_translation", [])
    write_manifest(snapshot)
    with pytest.raises(source.SourceError, match="nonempty"):
        source.prepare_source(snapshot)
