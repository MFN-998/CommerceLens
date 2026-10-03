# Local artifact cleanup review — 2026-10-02

Status: CLEANUP COMPLETE. Owner approved A/B, retained C and delegated the D decision;
A/B/D were removed after revalidation. Assessment and pre-deletion checkpoint: 0096260.
Scope: resource cleanliness only, before resuming geolocation staging. This is not the
post-Phase 3 engineering/product governance audit. No code, dependencies, database or
Phase 3 functionality was changed. Source baseline: published commit 484249b.
The proposal inventory below is retained as the exact historical deletion scope.

## Findings and practical impact

Tracked source, tests, configuration, migrations, active assets and historical project
evidence have valid uses. No tracked file was verified obsolete enough for deletion.
The main clutter is ignored local copies/generated output: .artifacts contained
43,529 files and 1,009,911,062 bytes (963.13 MiB) before the small preservation backup.
Normal Git-aware searches and the current selected quality commands exclude these
artifacts. There is no measured evidence they caused the recent implementation delays.
They increase disk/backup/inventory work and make broad recursive searches or manually
opening old source/manifest copies more confusing. Cleanup is recommended housekeeping,
not a claimed solution to all development delays.

## Proposed bounded deletion groups

All folder proposals include their contents. Only these 29 explicitly listed roots
are proposed; not the entire .artifacts directory. Total: 949,054,600 bytes,
approximately 905.09 MiB. Sizes count file lengths, not exact filesystem space reclaimed.

| Group | Recommendation | Contents | Approximate size |
| --- | --- | --- | --- |
| A | Recommended | One old validation working copy | 742.08 MiB |
| B | Recommended | Thirteen source-copy folders and ten ZIPs from completed scans/checkpoints | 12.84 MiB |
| C | Optional; retain as an offline fallback for now | Duplicate download of the nine canonical CSVs and transport marker | 120.34 MiB |
| D | Recommended housekeeping; lower priority | Retained generated test fixtures and obsolete bootstrap parse files | 29.83 MiB |

### A — Old isolated validation copy

Exact target: `D:\My Projects\CommerceLens\.artifacts\engineering-clean-20260920`.
It contains copied source/configuration plus its own .venv, web/node_modules, web/.next,
caches and old test fixtures: 30,908 files. It was used for the completed Phase 1–2
validation, not the current project environment. No tracked current command references
this path, no other process was detected pointing to it, and no reparse links were found.
Current commands use the main repository and its environments. No current project
functionality depends on this copy.

Deleting it removes that old local working environment and duplicate code/build output;
it does not remove the active .venv, frontend dependencies, source or Git history.
Fifty-seven non-generated source files matched Git history. This was a mixed validation
snapshot, not a single matching Git tree; do not promise bit-for-bit reconstruction of
the assembled environment. Historical source versions remain in Git, dependencies can
be installed from the appropriate lockfiles, and build/cache output can be regenerated
with the appropriate tools (installation may need network access).
Two unique draft documents and their exact bytes are preserved below before removal.
Keeping or archiving the whole copy elsewhere is safer if its complete old runtime
layout is wanted. Declining deletion has no current functional consequence, but keeps
most of the duplication and the possibility of inspecting stale code.

### B — Completed source scans/checkpoints

Every following name is under the exact parent
`D:\My Projects\CommerceLens\.artifacts\`:

| Exact name | Delete scope | Verified Git preservation / exact draft handling |
| --- | --- | --- |
| `atomic-load-checkpoint-export` | Folder and all contents | 35ba3c5 |
| `credential-checkpoint-export` | Folder and all contents | e428801 |
| `customer-acceptance-20260927-export` | Folder and all contents | 1785472 |
| `customer-prebuild-20260927-export` | Folder and all contents | 193be34 |
| `dbt-live-setup-20260925-export` | Folder and all contents | 142277c |
| `governance-20260927-export` | Folder and all contents | 47e35a7 |
| `m2-final-secret-snapshot` | Folder and all contents | 207b74f |
| `m2-preapply-secret-snapshot` | Folder and all contents | aa0104f |
| `m3-acceptance-export` | Folder and all contents | 2604e82 |
| `m3-landing-preapply-scan` | Folder and all contents | 625dbe8 |
| `phase3-m1-secret-snapshot` | Folder and all contents | 3e96ef9; exact WORK_STATE draft preserved separately |
| `provisioned-checkpoint-export` | Folder and all contents | 7cbf938 |
| `resume-checkpoint-export` | Folder and all contents | bcd85a9 |
| `atomic-load-checkpoint.zip` | ZIP file | 35ba3c5 |
| `credential-checkpoint.zip` | ZIP file | e428801 |
| `customer-acceptance-20260927.zip` | ZIP file | 1785472 |
| `customer-prebuild-20260927.zip` | ZIP file | 193be34 |
| `dbt-live-setup-20260925.zip` | ZIP file | 142277c |
| `engineering-audit-source.zip` | ZIP file | Source versions in Git; exact audit/standards drafts preserved |
| `governance-20260927.zip` | ZIP file | 47e35a7 |
| `m3-acceptance.zip` | ZIP file | 2604e82 |
| `provisioned-checkpoint.zip` | ZIP file | 7cbf938 |
| `resume-checkpoint.zip` | ZIP file | bcd85a9 |

These are exported source trees or compressed copies created for completed secret scans
and checkpoints. Current scanning uses committed Git history and staged contents in
memory; these older copies are not build, test, migration, dataset or credential inputs.
No tracked current code/configuration/workflow names these paths. Ordinary copies match
the historical commits above; the M1 draft differs only in unfinished validation/checkpoint
wording. The engineering source ZIP has the same two older drafts as group A, already
preserved. Finalized decisions/findings are present in tracked documents.

Git replaces their source-history/recovery purpose. Deletion removes redundant local
scan copies; it cannot remove commits or current source. Source exports can be generated
again from Git, although original ZIP metadata/compressed bytes need not be identical.
Exact unique draft bytes are retained below. Alternative: keep them ignored or archive
outside the working directory. Declining keeps duplicate old code without changing
functionality. Removing them reduces confusion and repeated inventory/backup overhead.

### C — Duplicate dataset download

Exact target: `D:\My Projects\CommerceLens\.artifacts\olist-download-v2`.
Contains the nine downloaded CSVs and a zero-byte transport completion marker under
.complete (ten files total). Every CSV's byte length and SHA-256 match both
`data/raw/olist-v2` and the tracked source manifest. Source ingestion, verification and
warehouse loading use the authoritative raw directory, not this named download copy;
no tracked command references its path.

Deleting this removes a redundant second local dataset copy, including its usefulness
as an offline fallback if the authoritative raw copy were lost. It does not change raw
data, the manifest, Phase 2 local staging or Supabase. The CSVs can currently be copied
from the retained verified raw snapshot; downloading pinned version 2 again would need
network/Kaggle access. The transport marker is generated by the downloader.
Safer alternative: retain or relocate this second copy as an intentional backup.
Declining costs 120.34 MiB but provides a local fallback. Git does not store these CSVs;
this proposal explicitly preserves the authoritative data.

### D — Generated test and obsolete parse output

Exact targets, including all contents:

- `D:\My Projects\CommerceLens\.artifacts\pytest` — 9,784 retained synthetic fixture files, about 25.55 MiB.
- `D:\My Projects\CommerceLens\.artifacts\pytest-offline-loading` — 1,015 old synthetic loading-test files, about 1.01 MiB.
- `D:\My Projects\CommerceLens\.pytest-tmp` — 1,091 legacy test scratch files, about 2.20 MiB.
- `D:\My Projects\CommerceLens\dbt\target` — five obsolete 2026-09-22 bootstrap parse files, about 1.06 MiB.

These contain generated fixture/mock project data and old parser manifests/caches, not
the live warehouse or canonical project datasets. Current tests create fresh UUID
fixture directories through conftest.py; current dbt commands explicitly use unique
.artifacts/dbt targets with partial parsing disabled. The legacy .pytest-tmp path is
still named by the default pytest configuration, but existing prior-run contents are
not required; generated parents/fixtures are recreated as needed. No reparse links were
found in these four roots. Current database acceptance evidence/artifacts remain retained.

Deletion loses the ability to inspect those exact old test fixture directories/parse
outputs. Tests and parser runs can regenerate new outputs, not necessarily the identical
historical directory IDs/metadata. No source/configuration/lockfile or test implementation
is removed. Direct dbt CLI users would regenerate the default parser cache if needed;
the supported runner already ignores it. Safer alternative: retain these for debugging
or remove only selected groups later. Declining has no functional consequence, but the
retained test fixtures continue to accumulate. Approval covers this cleanup only; future
automatic cleanup by tools still needs the established permission or a safe retained mode.

## Exact drafts preserved; keep this backup

Created and byte-verified before proposing deletion:
`D:\My Projects\CommerceLens\.artifacts\cleanup-preserved-20261002`.
Three drafts total 30,634 bytes plus a SHA-256 manifest:

- engineering-clean-20260920/docs/engineering-audit-phase-1-2.md
- engineering-clean-20260920/docs/engineering-standards.md
- phase3-m1-secret-snapshot/WORK_STATE.md

Current tracked audit/standards and published M1 commit 3e96ef9 preserve all substantive
decisions/findings and finalize old pending statements. Their exact draft bytes were
not recoverable from Git; the small backup preserves those bytes. This backup and its
manifest are excluded from every proposed deletion group.

## Resources to retain

Keep current source/configuration, all tests, migrations/privilege checks, master plan,
ADRs, historical phase/evidence documents, WORK_STATE, raw/interim datasets and manifest,
credentials/certificates/environment files, .git, active .venv/web/node_modules/web/.next,
current .artifacts/dbt acceptance output, .artifacts/tools, engineering-audit captures,
and the small preserved-drafts backup. Root Python caches are not a priority: they are
small or useful for normal tool performance. web/CLAUDE.md is an AGENTS adapter, not a
duplicate instruction set; the application icon and later-phase scaffolding are active.

## Documentation confusion; fix wording, not files

Historical findings below were maintenance follow-ups, not deletion targets.
Resolved in the 2026-10-03 geolocation unit: README/phase progress, setup-plan historical
label, retained fixture-location wording and staged scan guidance now match actual use.

- README.md still says dbt models are next; it should describe eight accepted staging sources.
- The Phase 3 plan's M1 cell should say design complete and implementation tracked in M2–M5.
- The dbt setup plan should be clearly labeled as its historical setup plan.
- development.md and CONTRIBUTING.md describe the old .pytest-tmp fixture location;
  retain current customer-staging.md commands and update those descriptions to the UUID
  fixture policy and explicit deletion restrictions.

Do not remove historical plans or status documents merely because newer status exists.

## Verification and approval boundary

Completed: clean baseline Git/history inspection, tracked reference review, inventory
and sizes, Git-content comparisons, nine CSV hash/size comparisons, old-copy process/link
checks, generated-root link checks and exact three-draft preservation. No source contents,
review records, private environment values or credentials were published. No tests/builds
or database actions were needed or run for this resource assessment.

Owner decision on 2026-10-02: delete A and B, keep C, and choose D based on future use.
D was removed because its existing old contents are not future inputs. Current conftest.py
creates fresh UUID fixture directories with parents; the supported dbt runner creates
fresh UUID targets and disables partial parsing. Future generated output may be created
normally, but this approval does not authorize automatic future artifact deletion.

Execution COMPLETE: 28 exact roots / 43,967 files / 822,867,605 bytes (784.75 MiB)
removed from A/B/D. Before removal all absolute roots were checked inside the repository,
with no reparse links or active process use; sizes still matched the reviewed inventory.
Three unique draft originals and preserved copies matched their recorded SHA-256 values.
The native PowerShell operation used literal paths, recording each completed removal in
.artifacts/cleanup-preserved-20261002/cleanup-result.json for interruption recovery.

Post-removal verification PASS: all 28 roots absent; 858 retained tracked/local files
hash-unchanged, including source, interim data, credentials, current dbt acceptance output,
tools, audit captures and preserved drafts. All nine authoritative CSVs and all nine
retained C copies passed manifest size/SHA-256 verification again after removal. Preserved
draft hashes also passed again. Active environments, Git and the explicitly retained roots
remain present. Only this report, the proposal JSON and WORK_STATE were modified in Git.
No tests/builds, package installation, migration or database action ran for this cleanup;
source/configuration were unchanged, so relevant checks were resource integrity and disuse.

Geolocation staging is the next implementation unit from the existing master plan.
The recorded documentation wording follow-ups were corrected on 2026-10-03. The comprehensive
governance audit still waits until Phase 3 is complete and verified.
