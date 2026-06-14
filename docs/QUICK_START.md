# Quick Start

## Install

```powershell
python -m pip install -r requirements.txt
npm install
```

## Start The Desktop App

```powershell
.\scripts\dev.ps1
```

Create a project, add a drawing set PDF, add optional CSV/XLSX reference files, validate inputs, choose a profile, run review, review findings, then export the packet.

## Useful Development Commands

```powershell
.\scripts\backend.ps1
.\scripts\test.ps1
.\scripts\build.ps1
.\scripts\generate_sample.ps1
```

## Real Drawing Sets

Use real client/company drawings only as local project inputs or local training inputs. Do not commit proprietary PDFs.

Private smoke inputs should go under the ignored folder:

```powershell
New-Item -ItemType Directory -Force local_test_inputs
```

Then create a project in the UI or through tests using files from that folder. Keep notes about false positives, OCR issues, title block issues, and performance in local-only files.

## Manual UI QA

Before a handoff, run the checklist in [Desktop UI QA Checklist](UI_QA_CHECKLIST.md).
