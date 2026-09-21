"""Faithful, bounded-memory source reading and deterministic landing evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from src.ingestion.olist import DATASET_HANDLE, sha256_file, verify_raw
from src.validation.contracts import TABLES

LANDING_CONTRACT_VERSION = 1
LOAD_NAMESPACE = UUID("74ff71ee-1aec-49c8-8f0a-a903e259ac47")
MONEY_COLUMNS = {
    "order_items": ("price", "freight_value"),
    "order_payments": ("payment_value",),
}
MONEY_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")
MONEY_LIMIT = Decimal("9999999999999999.99")


class SourceError(ValueError):
    """Source landing failed without reflecting source values in the diagnostic."""


class Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


@dataclass(frozen=True)
class TableEvidence:
    rows: int
    content_sha256: str
    money: dict[str, str]


@dataclass(frozen=True)
class SourcePlan:
    manifest: dict
    fingerprint: str
    load_id: UUID
    manifest_sha256: str
    tables: dict[str, TableEvidence]


def update_digest(digest: Digest, row_ordinal: int, rowvalues: Sequence[str]) -> None:
    """Frame record width, ordinal, and UTF-8 fields without delimiter ambiguity."""
    if row_ordinal < 1:
        raise ValueError("Source row ordinals must be positive")
    digest.update(len(rowvalues).to_bytes(4, "big"))
    for value in (str(row_ordinal), *rowvalues):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)


def iter_source_rows(root: Path, name: str) -> Iterator[tuple[str, ...]]:
    """Yield original text; the ordinal is a logical CSV record, not a text line."""
    if name not in TABLES:
        raise SourceError("Unknown source table")
    contract = TABLES[name]
    path = root / "data/raw/olist-v2" / contract.filename
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)
            if header is None or tuple(header) != tuple(contract.columns):
                raise SourceError(f"Source header differs from the contract: {name}")
            for row in reader:
                if len(row) != len(contract.columns):
                    raise SourceError(f"Source record width differs from the contract: {name}")
                if any("\x00" in field for field in row):
                    raise SourceError(f"Source record contains an unsupported NUL: {name}")
                yield tuple(row)
    except (csv.Error, UnicodeError):
        raise SourceError(f"Source CSV decoding failed: {name}") from None


def parse_money(value: str) -> Decimal:
    """Reject values PostgreSQL could round, overflow, or interpret as non-finite."""
    if MONEY_PATTERN.fullmatch(value) is None:
        raise SourceError("Money must be nonnegative decimal text with at most two decimals")
    amount = Decimal(value)
    if amount > MONEY_LIMIT:
        raise SourceError("Money exceeds the numeric(18,2) range")
    return amount


def prepare_source(root: Path) -> SourcePlan:
    """Verify immutable source bytes and compute exact text/amount reconciliation."""
    manifest = verify_raw(root)
    manifest_path = root / "data/source-manifest.json"
    manifest_sha256 = sha256_file(manifest_path)
    identity = {
        "dataset_handle": DATASET_HANDLE,
        "landing_contract_version": LANDING_CONTRACT_VERSION,
        "files": [[name, record["sha256"]] for name, record in sorted(manifest["files"].items())],
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    tables = {}
    for name, contract in TABLES.items():
        digest = hashlib.sha256()
        rows = 0
        money_columns = MONEY_COLUMNS.get(name, ())
        indexes = {column: tuple(contract.columns).index(column) for column in money_columns}
        sums = dict.fromkeys(money_columns, Decimal(0))
        # The verified Olist snapshot has fewer than two million rows. Forty digits
        # comfortably retain exact sums of numeric(18,2), independent of caller context.
        with localcontext() as context:
            context.prec = 40
            for rows, values in enumerate(iter_source_rows(root, name), 1):
                update_digest(digest, rows, values)
                for column, index in indexes.items():
                    sums[column] += parse_money(values[index])
            if rows == 0:
                raise SourceError(f"Expected a nonempty source table: {name}")
            tables[name] = TableEvidence(
                rows,
                digest.hexdigest(),
                {column: format(total, ".2f") for column, total in sums.items()},
            )
    if verify_raw(root) != manifest or sha256_file(manifest_path) != manifest_sha256:
        raise SourceError("Source provenance changed during preparation")
    return SourcePlan(
        manifest, fingerprint, uuid5(LOAD_NAMESPACE, fingerprint), manifest_sha256, tables
    )
