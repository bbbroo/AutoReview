# Current MVP Status

Last verified: 2026-06-14.

## Implemented Architecture

AutoReview currently has a local Electron, React, TypeScript desktop UI in `apps/desktop`, a local FastAPI sidecar in `apps/backend`, and the deterministic Python review engine in `ng_drawing_qa`.

The primary production workflow uses one persisted path:

1. The UI calls the FastAPI sidecar.
2. The sidecar stores projects, files, runs, progress, findings, training labels, and packet exports in SQLite.
3. A Python worker calls `ng_drawing_qa.services.review.run_project_review`.
4. Findings are persisted with stable fingerprints and project-level issue IDs.
5. Packet export calls `ng_drawing_qa.services.packet.export_review_packet` after reviewer decisions.

The direct-PDF CLI remains available for terminal workflows. It now creates a transient local project in the requested output folder, ingests files through the same file service, runs `run_project_review`, persists findings with the same issue IDs and fingerprints, and exports packets through `export_review_packet`.

## What Works

- Local-only desktop app startup through `.\scripts\dev.ps1`.
- Project creation/opening with `project.sqlite`.
- File ingestion, role inference, role editing, hashing, and project-local copies.
- Validation for missing files, blank files, unsupported extensions, unreadable PDFs, low-searchability PDFs, malformed tables, missing required columns, blank reference tags, duplicate reference keys, suspicious reference values, bad saved mappings, and DOCX placeholders.
- Reference analysis API and Input Files preview show inferred/saved/effective column mappings, required fields, row counts, parsed sample rows, and mapping warnings before running QA.
- Input Files now includes an in-place mapping editor for CSV/XLSX references so users can save role-based mappings without leaving the desktop workflow.
- Reusable role-based reference column mappings are stored locally under `profiles/reference_mappings.json` and included in profile export/import.
- Review runs through an isolated Python worker.
- Worker launch failures and expected worker-side errors are reported with friendly AutoReview messages instead of raw Python tracebacks.
- Finding persistence with stable `AR-####` issue IDs and deterministic fingerprints.
- Run manifests and `finding_traceability.csv` include compact issue ID/fingerprint traces for CLI-vs-persisted comparison and regression audits.
- Reviewer updates for status, severity, discipline, owner, edited message, RFI flag, and notes.
- Reviewer decision history is persisted for changed finding fields and exposed through the findings API/UI.
- Findings Review shows rule explanation, false-positive notes, confidence, matched text, source sheet/page, reference source fields when available, fingerprint, original/edited comments, notes, owner, RFI flag, reviewer action guidance, and decision history.
- Packet export after reviewer decisions.
- Packet export is blocked until the selected review run is completed.
- Default packet scope excludes rejected findings and includes accepted edited comments.
- Packet exports record mode (`internal_qa`, `client_review`, `backcheck`, or `full_debug`) separately from deterministic finding scope.
- Packet PDFs include bookmarks for major sections and drawing-page finding clusters.
- Issue IDs in the packet front matter link to the related marked-up drawing page when the PDF viewer supports internal links.
- Coordinate-backed drawing markups include visible `AR-####` labels on marked-up drawing pages.
- CLI direct-PDF runs use the same persisted review workflow as UI/backend runs while preserving existing commands.
- Run history and comparison show new, resolved, repeated, carryover, status-changed, severity-changed, message-changed, and backcheck-required findings.
- Training labels, missed findings, golden regression, and per-rule regression performance summaries with accepted count/rate.
- Support exports including CSV, XLSX, Markdown, HTML, logs, and diagnostics.

## Verification Results

Automated verification:

```powershell
python -m pytest
npm --workspace apps/desktop run test
npm --workspace apps/desktop run build
```

Current Python suite covers backend API validation, project creation, file ingestion, role inference/assignment, reference analysis, saved reference mappings, malformed references, run creation, worker launch failure handling, friendly worker errors, finding persistence, finding updates, reviewer decision history, packet export, packet export status validation, packet modes/scopes, packet bookmarks, packet issue links, visible issue-ID labels on drawing markups, categorized run comparison including backcheck-required findings, training labels, accepted-rate rule performance summaries, profile import/export, packet filtering, edited comments, rejected-finding exclusion, fingerprint stability, traceability exports, and CLI-vs-persisted workflow consistency. The React UI tests cover the finding trust panel, reference preview/mapping editor, and a mocked project-to-packet workflow through the local API surface.

Sample project smoke:

- Generated sample inputs in ignored `local_samples/`.
- Ran the persisted project workflow.
- Accepted, edited, and rejected findings.
- Exported a packet.
- Confirmed issue index, priority list, marked-up drawings, rendered reference inputs, source map, stable issue IDs, edited accepted wording, and rejected finding exclusion.
- Confirmed packet bookmarks, issue-index links, and visible drawing-page issue-ID labels on generated sample packets.

Private real-PDF smoke:

- Used `C:\Users\brook\Downloads\20250508_Alliant Sheboygan Skid Upgrade_IFC.pdf` locally only.
- Copied test data under ignored `local_test_inputs/`.
- Drawing-only conservative run completed without references.
- Source size: 112,244,388 bytes.
- Page count: 123.
- Elapsed review time: about 39 seconds.
- Findings: 26.
- Packet page count: 130.
- Packet included issue index, marked-up drawings, rendered reference section, source map, and accepted edited wording.
- Observed finding types: low-searchable-text/OCR warnings, raster-like pages, duplicate sheet number findings, pressure consistency, and detail reference checks.

## Current Gaps

- The desktop UI does not yet have automated visual regression coverage.
- Decision history is local single-user only; there is no reviewer identity/permissions model by design.
- DOCX support is text extraction only, not print-fidelity rendering.
- Reference PDFs are preserved/rendered, but structured reconciliation still depends on CSV/XLSX columns.
- Reference mapping editing is API-backed and previewed in the UI, but the UI does not yet provide a full column-mapping editor.
- Title block extraction uses numeric configured regions and needs per-company tuning.
- Large real drawings can generate noisy duplicate-sheet or low-searchability findings that need profile tuning.
- CLI output now includes a transient project structure (`project.sqlite`, `inputs`, `profiles`, `packets`) inside the requested output folder rather than only loose report files.
- Electron packaging, installer, updater, signing, and release process are documented but not implemented.
- No enterprise auth, licensing, cloud sync, or tenant model is implemented by design.

## Highest-Risk Areas

- PDF text quality and OCR variability on scanned or mixed raster/vector drawings.
- Company-specific title block regions and sheet-number conventions.
- False positives in duplicate sheet and reference/callout checks on real project drawing sets.
- CLI and UI now share the persisted workflow, but the terminal output folder layout changed and should be verified with internal users.
- Electron/Vite/Vitest audit findings that require major dependency upgrade testing.

## npm Audit Triage

`npm audit` currently reports findings in development/runtime tooling:

- `electron`: high/moderate/low advisories fixed only by a semver-major Electron upgrade.
- `vite`, `esbuild`, `@vitejs/plugin-react`: dev-server/build-chain advisories fixed only by semver-major Vite/plugin upgrades.
- `vitest`, `vite-node`, `@vitest/mocker`: test tooling advisories fixed by semver-major Vitest upgrades.
- `concurrently` via `shell-quote`: command-runner development dependency. `npm audit fix` was attempted without `--force` and made no dependency changes; defer to a dependency compatibility pass or replace the dev command runner.

Do not run `npm audit fix --force` in this repo without a dedicated dependency upgrade branch and full desktop smoke testing.

## Private Drawing Inputs

Use `local_test_inputs/` for private smoke inputs. This folder is ignored by Git. Do not commit, package, or upload proprietary PDFs or client reference files.

Recommended layout:

```text
local_test_inputs/
  project_name/
    source_pdfs/
    references/
    notes.md
```

## Next Development Phase

1. Add automated UI/e2e tests around project setup, file selection, run status, findings edits, filters, and packet export.
2. Add company-specific profile tuning from labeled real examples.
3. Broaden golden regression sets with synthetic regulator station, P&ID, and drawing-index mismatch cases, then use per-rule summaries to tune noisy rules.
4. Improve finding evidence display and rule explanation panels in the UI.
5. Plan Electron/Vite/Vitest/Electron major dependency upgrades in a controlled compatibility branch.
