# Category translation staging milestone

Phase 3 M4, 2026-09-27. Reuses the existing selected runner, restricted transformer,
view materialization and retained artifacts. No dependencies or schema migrations.

One retained source row per Portuguese product_category_name. English translations may
repeat; they are not a key. Preserve literal text, accents, case, whitespace and lineage;
only exact empty text becomes NULL. Missing mandatory values and duplicate Portuguese
keys fail tests without filtering rows or inventing translations. The known 13 product
rows without translation coverage remain a separate warning. No product join is added.

Eight dbt tests cover four non-null columns, Portuguese key uniqueness, positive ordinal,
composite lineage uniqueness and bidirectional full-row EXCEPT ALL reconciliation.
Five synthetic tests exercise the real projection including repeated English translations,
conflicting Portuguese keys, missing values and invalid/duplicate lineage.

Use the retained checks and recovery guidance in [customer staging](customer-staging.md).

```powershell
.venv/Scripts/python.exe -B -m src.warehouse dbt-build --select stg_category_translation
.venv/Scripts/python.exe -B -m src.warehouse dbt-test --select stg_category_translation
```

Read-only acceptance: tests/test_warehouse_category_translation_integration.py with
COMMERCE_WAREHOUSE_CATEGORY_TRANSLATION_INTEGRATION=1. Enable only the intended test.
Data tests follow view commit; a failed test requires diagnosis, not a claim of rollback.

Status: prepared; repository validation and live build/acceptance pending.
