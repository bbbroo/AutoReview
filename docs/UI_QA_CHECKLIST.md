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
6. Click Analyze References.
7. Confirm reference preview shows inferred/saved/effective mappings, required fields, row counts, sample rows, and file-specific warnings.
8. In the Column Mapping editor, map at least one unusual header such as `Valve ID` to tag / line number and save it.
9. Confirm the saved mapping is reflected in the effective/saved mapping summary and persisted under the project profile.
10. Confirm missing drawing sets, blank files, unsupported formats, unreadable PDFs, malformed spreadsheets, missing required columns, blank reference tags, duplicate reference keys, suspicious reference values, stale mappings, DOCX placeholders, and low-searchability warnings show as readable messages.

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
3. Select a finding and confirm details show issue ID, message, original generated text, edited text, evidence, matched text, sheet/page, output PDF page, coordinates, placement type, coordinate source, placement confidence, placement warning, confidence, fingerprint, rule metadata, false-positive notes, owner, RFI flag, and reviewer notes.
4. Confirm the detail panel says the finding is a deterministic draft finding, not an engineering approval.
5. Confirm Rule Explanation shows rule ID/name, description, discipline, default severity, default confidence, required inputs, profiles, and false-positive notes.
6. Confirm Finding Evidence shows why the item was flagged, what the reviewer should do next, matched text, context, sheet/page, fingerprint, and any linked reference source/row.
7. Confirm Decision History is empty before edits or shows prior status/comment/severity/discipline changes after edits.
8. Accept one finding.
9. Reject one finding.
10. Edit the wording on one accepted finding.
11. Change severity and discipline on one finding.
12. Assign an owner.
13. Mark one finding as RFI candidate.
14. Confirm changes persist after navigating away and back.
15. Confirm Decision History lists each changed field with old value, new value, timestamp, and `local_user`.

## Packet Export

1. Open Packet Export.
2. Confirm Packet Mode defaults to internal QA and Finding Scope defaults to accepted only.
3. Export with default accepted-only scope.
4. Open the packet in Bluebeam or the system PDF viewer.
5. Confirm the PDF bookmark/sidebar outline includes the cover, issue index, critical/major list, marked-up drawing set, rendered reference inputs, and source map.
6. Click at least one issue ID in the issue index and confirm it jumps to the related marked-up drawing page when the viewer supports internal links.
7. On a marked-up drawing page, confirm coordinate-backed findings show a visible `AR-####` issue-ID label near the highlighted evidence.
8. Confirm resolved text-search findings show a rectangle around the searched text and are marked as `resolved_text_search` in finding evidence or diagnostics.
9. Confirm title-block findings use the configured title-block region rather than a generic page callout when possible.
10. Confirm findings without usable coordinates but with a valid page number show a stacked page-level callout box on the related drawing page. The callout should include issue ID, severity, rule ID, and edited reviewer wording.
11. Confirm reference-only findings are present in the issue index/reference evidence but do not appear as misleading exact drawing-location rectangles.
12. Check `outputs/runs/{run_id}/run_manifest.json` and confirm `packet_markup_counts` reports exact-location, resolved-search, title-block, page-level, reference-only, and unplaced counts.
13. Open `outputs/runs/{run_id}/placement_debug.csv` and confirm placement type, coordinate source, confidence, resolved text, and warning fields are populated.
14. Confirm the packet contains:
   - Cover/disclaimer.
   - Issue summary and issue index.
   - Critical/major list.
   - Accepted edited findings.
   - Marked-up drawing pages.
   - Rendered reference input section.
   - Source map.
15. Confirm rejected findings are absent from the default packet.
16. Change Packet Mode to backcheck and confirm Finding Scope changes to backcheck.
17. Export a backcheck packet after marking a finding as Backcheck Required or Needs Review, then confirm accepted-only findings are absent and backcheck findings are present.
18. Change Packet Mode to full debug and confirm Finding Scope changes to all.
19. Export with a broader scope and confirm draft, non-rejected, or rejected findings appear when selected, including page-level callouts for coordinate-less findings.

## Run History And Comparison

1. Run the same sample project twice.
2. Open Run History.
3. Compare latest runs.
4. Confirm new, resolved, repeated, carryover, status-changed, severity-changed, message-changed, backcheck-required, and changed counts render.
5. Confirm issue IDs remain stable for matching fingerprints.

## Training

1. Create a training set from a completed run.
2. Mark a finding as false positive.
3. Add a missed finding.
4. Run regression.
5. Confirm expected, actual, missing, new, changed, false-positive, and missed counts render.
6. Confirm the per-rule performance table lists expected, actual, accepted, accepted rate, matched, missing, new, changed, false-positive, and missed counts.

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
