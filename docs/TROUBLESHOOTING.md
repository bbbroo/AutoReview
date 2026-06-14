# Troubleshooting

## Backend Unavailable

Run:

```powershell
.\scripts\backend.ps1
```

Then check:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/health
```

If Electron cannot start the sidecar, start from the repository root and confirm Python dependencies are installed:

```powershell
python -m pip install -r requirements.txt
.\scripts\dev.ps1
```

The UI should show a readable backend error instead of a Python traceback.

## Review Worker Failed

If a run fails, open Run Status or Run History first. The run record, progress events, and `outputs/runs/{run_id}/run_manifest.json` should contain the friendly failure message and recommended fix.

Worker stderr logs under `logs/{run_id}.worker.err.log` should report concise AutoReview error codes such as `MISSING_INPUT` or `VALIDATION_ERROR`, not raw Python tracebacks, for expected user-fixable failures.

## Missing Or Unreadable Files

If validation reports a missing file, re-add the file from its current location. If a copied project input was deleted manually, remove and re-ingest the file.

Unreadable PDFs usually mean the file is not a valid PDF, is encrypted, or is damaged. Open it in Bluebeam or a system PDF viewer, repair/export a clean PDF, then ingest it again.

Blank files are blocked. Replace them with the real drawing or reference file.

Unsupported files should be converted to PDF, CSV, XLSX, XLSM, DOCX, or TXT depending on the intended role.

## Low Searchable Text

Run OCR in Bluebeam or another approved OCR workflow, then rerun validation. Raster-heavy drawings can still be included, but tag checks depend on searchable text.

## Missing Spreadsheet Columns

The validator reports missing expected columns. Rename columns or adjust mappings in the profile/config before running.

For MVP reconciliation, CSV/XLSX files need recognizable columns such as `sheet_number`, `tag`, `line_number`, `instrument_tag`, or `equipment_tag` depending on role. PDF references are preserved as evidence but are not yet structured table inputs.

Use Input Files -> Analyze References to inspect inferred, saved, and effective mappings. If a real reference uses unusual headers, save a role-based mapping in `profiles/reference_mappings.json` or through the local reference mapping API. Stale saved mappings are reported as `BAD_COLUMN_MAPPING`.

## Blank Or Duplicate Reference Tags

Reference validation reports blank mapped keys and duplicate mapped keys before the review run. Fix the source list where possible. If duplicates are intentional, document the reason in project notes and consider a project-specific suppression/profile rule later.

## Suspicious Reference Values

`SUSPICIOUS_REFERENCE_VALUES` means many mapped identifiers or pressure values do not look like the expected role. Common causes are a wrong mapped column, a title/description column being treated as a tag column, or pressure text that needs cleanup before deterministic comparison.

## Packet Has No Findings

Default packet scope is accepted findings only. Accept findings in the review screen or choose a broader export scope.

## DOCX References

DOCX files are accepted as supplemental references. The MVP renders extracted text where possible; direct Word print fidelity is planned later.

## npm Audit Findings

The current desktop dependency tree reports npm audit findings in Electron, Vite/esbuild, Vitest, and concurrently/shell-quote. A non-force audit fix does not currently produce a safe lockfile update. Do not run `npm audit fix --force` without a dedicated dependency-upgrade branch because it introduces semver-major Electron/Vite/Vitest changes that need compatibility testing.

See [Current MVP Status](MVP_STATUS.md) for the latest triage.
