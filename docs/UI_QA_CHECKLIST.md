# Desktop UI QA Checklist

Use this checklist before handing the MVP to an internal engineering reviewer. Automated visual regression is not yet part of the repo, so this is the manual QA script for the current build.

## Start App

1. Run:

   ```powershell
   .\scripts\dev.ps1
   ```

2. Confirm Electron opens AutoReview.
3. Confirm the sidebar shows Project Setup, Input Files, Profiles & Rules, Run Status, Findings Review, Packet Export, Run History, Training, and Settings.
4. Confirm the backend status changes to available after the sidecar starts.
5. If backend remains unavailable, click Refresh and check `.\scripts\backend.ps1`.

## Project Setup

1. On Project Setup, enter a project name.
2. Browse to or type a local parent folder.
3. Click Create Project.
4. Confirm the app navigates to Input Files.
5. Close and reopen the app, then confirm the project appears in Recent Projects.
6. Use Open Project against the project folder and confirm it reopens prior runs.

## Input Files

1. Add a drawing set PDF.
2. Add optional CSV/XLSX references: drawing index, valve list, line list, instrument index, equipment list.
3. Confirm inferred file roles are reasonable.
4. Change at least one file role manually and confirm the table updates.
5. Click Validate.
6. Confirm missing drawing sets, blank files, unsupported formats, unreadable PDFs, malformed spreadsheets, missing required columns, DOCX placeholders, and low-searchability warnings show as readable messages.

## Profiles And Rules

1. Open Profiles & Rules.
2. Select balanced, conservative, aggressive, regulator station, P&ID, and pipeline crossing profiles.
3. Confirm rule metadata remains visible and readable.
4. Confirm AI comment drafts and symbol-recognition stub are not presented as enabled deterministic review rules by default.

## Run Status

1. Start a review from Run Status.
2. Confirm progress events update without freezing the UI.
3. Confirm run ID, profile, output folder, start/completion times, warning count, and errors are visible.
4. If a run fails, confirm the error text is friendly and the run remains in history.
5. Confirm the run output folder contains `run_manifest.json`, support CSV/XLSX/HTML/Markdown files, and logs.

## Findings Review

1. Open Findings Review after a completed run.
2. Filter by severity, status, discipline, rule, sheet, RFI, and text.
3. Select a finding and confirm details show issue ID, message, original generated text, edited text, evidence, matched text, sheet, coordinates, rule metadata, and reviewer notes.
4. Accept one finding.
5. Reject one finding.
6. Edit the wording on one accepted finding.
7. Change severity and discipline on one finding.
8. Mark one finding as RFI candidate.
9. Confirm changes persist after navigating away and back.

## Packet Export

1. Open Packet Export.
2. Export with default accepted-only scope.
3. Open the packet in Bluebeam or the system PDF viewer.
4. Confirm the packet contains:
   - Cover/disclaimer.
   - Issue summary and issue index.
   - Critical/major list.
   - Accepted edited findings.
   - Marked-up drawing pages.
   - Rendered reference input section.
   - Source map.
5. Confirm rejected findings are absent from the default packet.
6. Export with a broader scope and confirm draft/non-rejected findings appear when selected.

## Run History And Comparison

1. Run the same sample project twice.
2. Open Run History.
3. Compare latest runs.
4. Confirm repeated findings are listed and issue IDs remain stable for matching fingerprints.

## Training

1. Create a training set from a completed run.
2. Mark a finding as false positive.
3. Add a missed finding.
4. Run regression.
5. Confirm expected, actual, missing, new, changed, false-positive, and missed counts render.

## Settings

1. Confirm Settings shows local-only backend status.
2. Confirm project database path is visible when a project is open.
3. Confirm current profile and deterministic rule count are visible.

## Private Real-PDF Smoke

1. Place private PDFs under `local_test_inputs/`.
2. Create a local project from that folder.
3. Add one private drawing set PDF.
4. Run validation and review without reference files.
5. Accept one finding and export a packet.
6. Record page count, elapsed time, warnings, finding count, OCR/searchability issues, and obvious false positives in local notes only.

Do not commit screenshots or proprietary drawing files unless they are synthetic samples created specifically for the repo.
