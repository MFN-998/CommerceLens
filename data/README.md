# Olist data setup and provenance

Phase 2 uses the **Brazilian E-Commerce Public Dataset by Olist**, published by Olist
on [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The pinned
release is `olistbr/brazilian-ecommerce/versions/2`. Kaggle's source metadata lists
**CC BY-NC-SA 4.0**; see the [license](https://creativecommons.org/licenses/by-nc-sa/4.0/).
This attribution describes the dataset; it does not grant a software license.

These are historical, anonymized source records, not a live business feed. The observed
order-purchase range is September 2016 through October 2018. Do not infer the period
of every other event from that range.

## 1. Install the data tools

From the repository root in PowerShell:

```powershell
Set-Location 'D:\My Projects\CommerceLens'
uv sync --locked --group data
```

The `data` group contains pandas for typed tables, Pandera for executable contracts,
PyArrow for Parquet, and KaggleHub for the official download. Keeping it separate lets
the API foundation run without loading a data-processing stack. Include `--group data`
in subsequent data commands because uv synchronizes selected groups on each run.

## 2. Acquire the pinned snapshot

```powershell
uv run --locked --group data python -m src.ingestion.olist
uv run --locked --group data python -m src.ingestion.olist --verify
```

The first command downloads nine CSVs and preserves their exact bytes in `raw/olist-v2/`.
`source-manifest.json` records the source, version, acquisition time, license, byte sizes,
and SHA-256 hashes. A fresh clone already contains that manifest: acquisition restores
the raw files only if their hashes match it, preserving the original provenance record.
An existing raw snapshot is verified instead of overwritten or downloaded again.

An existing official download can be used without a network call:

```powershell
uv run --locked --group data python -m src.ingestion.olist --source-dir 'C:\path\to\olist-csvs'
```

Use a directory containing exactly the nine official CSVs. KaggleHub's `.complete`
transport-marker directory is tolerated on input but is not copied into raw data.
Extra/missing files, symbolic links, mismatching hashes, or raw files without a matching
manifest cause a failure. Do not edit raw files to bypass it.

The official public release was downloaded without credentials during setup. If Kaggle
requires authentication later, use its supported local credential flow described in
[KaggleHub's documentation](https://github.com/Kaggle/kagglehub); never put tokens in
this repository or reports. A blocked download is an access issue, not a reason to
substitute an unverified dataset mirror.

## 3. Validate and create local staging

```powershell
uv run --locked --group data python -m src.validation.run
```

The pipeline verifies raw hashes, inventories every column, checks source records,
parses explicit types, validates schemas and relationships, and profiles anomalies.
It verifies raw integrity again before publishing the complete staging snapshot at
`interim/olist-v2-v1/`. All nine Parquet files are read back and compared with their
in-memory tables, including types. The snapshot manifest records hashes and row counts.

Rerun the same command to verify identical existing output. It refuses to overwrite a
different snapshot. Report generation time and the staging action can change on a
rerun; the source provenance and data content must not change. Run one pipeline process
at a time; this is a local development workflow, not a concurrent job service.

The transformations are deliberately limited:

- Empty CSV fields become null. Literal text such as `NA`, whitespace, and review text
  remain unchanged. A UTF-8 byte-order mark is handled when reading, without editing raw bytes.
- Identifiers and ZIP prefixes remain strings. No invented zero-padding or trimming occurs.
- Nullable integers, floats, and timezone-naive timestamps get explicit types. Non-empty
  values that fail conversion are counted and block staging; they are not silently discarded.
  Integral decimals are parsed without a floating-point intermediate. Unsupported NUL
  characters are rejected before the CSV parser could truncate a field.
- Every row is retained, including repeated geography rows and multiple reviews. `_source_row`
  is the one-based logical CSV record ordinal, excluding the header, not a physical line number.

Exit code 0 means `PASS` or `PASS_WITH_WARNINGS`; exit code 1 means `FAIL` and blocks new
staging. Warnings permit a faithful source snapshot, not unrestricted analytical use.
Existing good staging remains intact when validation fails; consult the current report
before using it. A failure report can replace a previous report even though staging stays.

## 4. Read the evidence before using the data

- [Quality report](../docs/data-quality-report.md): inventory, positive checks, and interpretation.
- [JSON report](../docs/data-quality-report.json): all checks, ranges, nulls, hashes, and key counts.
- [Initial dictionary](../docs/data_dictionary/initial.md): all 52 source columns and observed keys.
- [Source/staging decisions](../docs/decisions/0002-source-quality.md): relationships and handoff rules.
- [Phase 2 completion](../docs/phase-2-status.md): verification evidence and limitations.

In particular, geography ZIP prefixes and individual review IDs are not unique. Joining
items and payments directly can multiply rows. Phase 3 must resolve join grains explicitly.

## 5. Run the offline checks

```powershell
uv run --locked --group data ruff check .
uv run --locked --group data ruff format --check .
uv run --locked --group data pytest
```

Tests use small synthetic data and need no Kaggle connection, real customer records,
database, or cloud credentials. They include raw tampering, malformed CSVs, failed
parsing, bad keys/references, staging protection, and repeatable Parquet round trips.

## Storage and recovery

Git tracks code, lockfiles, provenance metadata, dictionary, and quality reports. It
excludes `data/raw/`, `data/interim/`, and `.artifacts/`. Generated reports contain
aggregate diagnostics, not source customer/order IDs or review comments.

On a hash or staging mismatch, investigate the named file and source version first.
There is no force-overwrite option. Preserve an existing snapshot while deciding whether
a reviewed source or staging-format version change is needed. A terminated acquisition
may leave `.artifacts/olist-acquisition.lock`; validation may leave
`.artifacts/olist-validation.lock`. Confirm that no corresponding process is running
before removing only that lock directory and retrying. Do not delete the raw snapshot
or its manifest as a routine troubleshooting step.

Report files are replaced atomically one at a time, not as a multi-file transaction.
After an interruption, rerun validation to refresh JSON, Markdown, and the dictionary
together; compare their generation timestamps. The JSON report is authoritative.
A concurrent validation attempt fails without replacing the active run's reports.
Reports record only allowed categorical values and aggregate unknown counts; unexpected
input text must not leak into tracked failure reports.

PostgreSQL/Supabase, dbt, warehouse models, and analytical queries belong to Phase 3.
