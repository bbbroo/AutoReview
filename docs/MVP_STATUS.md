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

The legacy direct-PDF CLI remains available and shares extraction, reference loading, deterministic rules, annotation, reports, and packet builders. Its `process_one_pdf` orchestration is still separate from the persisted project workflow and should be collapsed into the same service contract in the next hardening phase.

## What Works

- Local-only desktop app startup through `.\scripts\dev.ps1`.
- Project creation/opening with `project.sqlite`.
- File ingestion, role inference, role editing, hashing, and project-local copies.
- Validation for missing files, blank files, unsupported extensions, unreadable PDFs, low-searchability PDFs, malformed tables, missing required columns, and DOCX placeholders.
- Review runs through an isolated Python worker.
- Finding persistence with stable `AR-####` issue IDs and deterministic fingerprints.
- Reviewer updates for status, severity, discipline, edited message, RFI flag, and notes.
- Packet export after reviewer decisions.
- Default packet scope excludes rejected findings and includes accepted edited comments.
- Run history, run comparison, training labels, missed findings, and golden regression foundation.
- Support exports including CSV, XLSX, Markdown, HTML, logs, and diagnostics.

## Verification Results

Automated verification:

```powershell
python -m pytest
npm --workspace apps/desktop run test
npm --workspace apps/desktop run build
```

Current Python suite covers backend API validation, project creation, file ingestion, role assignment, run creation, finding persistence, finding updates, packet export, run comparison, training labels, profile import/export, packet filtering, edited comments, rejected-finding exclusion, and fingerprint stability.

Sample project smoke:

- Generated sample inputs in ignored `local_samples/`.
- Ran the persisted project workflow.
- Accepted, edited, and rejected findings.
- Exported a packet.
- Confirmed issue index, priority list, marked-up drawings, rendered reference inputs, source map, stable issue IDs, edited accepted wording, and rejected finding exclusion.

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

- The legacy direct-PDF CLI still has separate orchestration from the persisted project workflow.
- The desktop UI does not yet have automated visual regression coverage.
- DOCX support is text extraction only, not print-fidelity rendering.
- Reference PDFs are preserved/rendered, but structured reconciliation still depends on CSV/XLSX columns.
- Title block extraction uses numeric configured regions and needs per-company tuning.
- Large real drawings can generate noisy duplicate-sheet or low-searchability findings that need profile tuning.
- Electron packaging, installer, updater, signing, and release process are documented but not implemented.
- No enterprise auth, licensing, cloud sync, or tenant model is implemented by design.

## Highest-Risk Areas

- PDF text quality and OCR variability on scanned or mixed raster/vector drawings.
- Company-specific title block regions and sheet-number conventions.
- False positives in duplicate sheet and reference/callout checks on real project drawing sets.
- Legacy CLI orchestration drift from the persisted worker workflow.
- Electron/Vite/Vitest audit findings that require major dependency upgrade testing.

## npm Audit Triage

`npm audit` currently reports findings in development/runtime tooling:

- `electron`: high/moderate/low advisories fixed only by a semver-major Electron upgrade.
- `vite`, `esbuild`, `@vitejs/plugin-react`: dev-server/build-chain advisories fixed only by semver-major Vite/plugin upgrades.
- `vitest`, `vite-node`, `@vitest/mocker`: test tooling advisories fixed by semver-major Vitest upgrades.
- `concurrently` via `shell-quote`: command-runner development dependency. A safe override attempt did not change the workspace resolution; defer to a dependency compatibility pass.

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

1. Collapse the legacy CLI orchestration into the persisted review service or a shared lower-level workflow contract.
2. Add automated UI/e2e tests around project setup, file selection, run status, findings edits, filters, and packet export.
3. Add company-specific profile tuning from labeled real examples.
4. Broaden golden regression sets with synthetic regulator station, P&ID, and drawing-index mismatch cases.
5. Plan Electron/Vite/Vitest/Electron major dependency upgrades in a controlled compatibility branch.
