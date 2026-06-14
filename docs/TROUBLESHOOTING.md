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

## Low Searchable Text

Run OCR in Bluebeam or another approved OCR workflow, then rerun validation. Raster-heavy drawings can still be included, but tag checks depend on searchable text.

## Missing Spreadsheet Columns

The validator reports missing expected columns. Rename columns or adjust mappings in the profile/config before running.

## Packet Has No Findings

Default packet scope is accepted findings only. Accept findings in the review screen or choose a broader export scope.

## DOCX References

DOCX files are accepted as supplemental references. The MVP renders extracted text where possible; direct Word print fidelity is planned later.

## npm Audit Findings

The current desktop dependency tree reports npm audit findings. Do not run `npm audit fix --force` without review because it can introduce breaking Electron/Vite upgrades.
