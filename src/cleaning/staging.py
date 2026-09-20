"""Read CSV values losslessly, then apply explicit nullable staging types."""

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from src.validation.contracts import INTEGER, TABLES, D, F

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def _integer(value):
    """Parse integral decimal values without a lossy intermediate float."""
    if pd.isna(value) or NUMBER.fullmatch(value.strip()) is None:
        return pd.NA
    try:
        number = Decimal(value)
        if not -(2**63) <= number < 2**63 or number != number.to_integral_value():
            return pd.NA
        return int(number)
    except InvalidOperation:
        return pd.NA


def read_source(path: Path, table: str) -> pd.DataFrame:
    expected = list(TABLES[table].columns)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if header != expected:
            raise ValueError(f"{path.name}: source columns do not match the contract")
        for record_number, record in enumerate(reader, start=1):
            if len(record) != len(expected):
                raise ValueError(f"{path.name}: wrong field count in source record {record_number}")
            if any("\0" in value for value in record):
                raise ValueError(f"{path.name}: NUL character in source record {record_number}")
    frame = pd.read_csv(
        path,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
        skip_blank_lines=False,
    )
    if frame.empty:
        raise ValueError(f"{path.name}: empty source table")
    return frame


def standardize(raw: pd.DataFrame, table: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Only empty CSV fields become null; invalid typed values are counted, never hidden."""
    spec = TABLES[table]
    if list(raw.columns) != list(spec.columns):
        raise ValueError(f"{table}: source columns do not match the contract")
    frame = raw.replace("", pd.NA).copy()
    failures = {}
    for name, column in spec.columns.items():
        source = frame[name]
        typed: pd.Series
        if column.dtype == INTEGER:
            typed = pd.Series(source.map(_integer), dtype=pd.Int64Dtype(), index=source.index)
        elif column.dtype == F:
            typed = pd.to_numeric(source, errors="coerce")
            invalid = typed.isin([float("inf"), float("-inf")])
            typed = typed.mask(invalid).astype(pd.Float64Dtype())
        elif column.dtype == D:
            typed = pd.to_datetime(source, format="%Y-%m-%d %H:%M:%S", errors="coerce")
            # Use ns consistently in the contract and Parquet round trips.
            typed = typed.where(typed.between(pd.Timestamp.min, pd.Timestamp.max)).astype(D)
        else:
            typed = source.astype("string")
        failures[name] = int((source.notna() & typed.isna()).sum())
        frame[name] = typed
    frame["_source_row"] = pd.array(range(1, len(frame) + 1), dtype="Int64")
    return frame, failures
