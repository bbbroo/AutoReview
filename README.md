# AutoReview

AutoReview is a local-first desktop application for natural gas drawing set QA. It combines an Electron, React, TypeScript desktop UI with a local FastAPI sidecar and deterministic Python PDF review engine.

The product output is one single-source review packet PDF: cover, review disclaimer, issue summary, issue index, accepted or selected findings, marked-up drawing pages, rendered reference inputs, and source map. CSV, Excel, Markdown, HTML, logs, and debug files remain support outputs.

## Current MVP

- Local Windows development workflow, no API keys required.
- Project folders with `inputs`, `outputs/runs/{run_id}`, `packets`, `logs`, `debug`, `profiles`, `training`, and `project.sqlite`.
- FastAPI sidecar for projects, files, validation, runs, findings, packet export, history, comparison, and training sets.
- Electron + React UI for project setup, file ingestion, profile selection, run progress, findings review, packet export, history, settings, and training.
- Reviewer workflow for accepting, rejecting, editing, reclassifying, and annotating findings before export.
- Findings review trust panel with rule explanation, evidence, reviewer action guidance, owner/RFI controls, notes, and decision history.
- Reference preview and profile-backed CSV/XLSX column mapping editor for common engineering reference lists.
- Deterministic rules with metadata for UI display.
- Golden training set foundation for false positives, missed findings, and regression checks.

See [Current MVP Status](docs/MVP_STATUS.md) for the latest verified architecture, known gaps, audit triage, and real-PDF smoke notes.

## Quick Start

```powershell
python -m pip install -r requirements.txt
npm install
.\scripts\dev.ps1
```

The dev script starts the desktop app. Electron launches the local FastAPI sidecar. In development, the React UI is served by Vite.

Backend only:

```powershell
.\scripts\backend.ps1
```

Tests:

```powershell
.\scripts\test.ps1
```

Build UI:

```powershell
.\scripts\build.ps1
```

Generate sample inputs:

```powershell
.\scripts\generate_sample.ps1
```

## CLI

The CLI remains available and uses the same persisted review workflow as the desktop app. Direct PDF runs create a local project-shaped output folder containing `project.sqlite`, copied inputs, support reports, marked-up PDF output, and the packet under `packets/`.

```powershell
python -m ng_drawing_qa.cli input.pdf --out-dir outputs
python -m ng_drawing_qa.cli --list-rules
python -m ng_drawing_qa.cli --generate-sample examples/generated_sample
```

Every persisted UI, worker, and CLI run writes the same deterministic trace outputs, including `run_manifest.json`, `issue_log.csv`, and `finding_traceability.csv` with stable issue IDs and fingerprints.

## Local-Only Security

AutoReview does not require cloud storage, authentication, external APIs, Bluebeam API access, or AI services. Drawing files and project data remain on the local computer by default. Future integrations must be optional and disabled by default.

## Documentation

- [Quick Start](docs/QUICK_START.md)
- [Current MVP Status](docs/MVP_STATUS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Desktop UI QA Checklist](docs/UI_QA_CHECKLIST.md)
- [Rule Authoring](docs/RULE_AUTHORING.md)
- [Training Sets](docs/TRAINING_SETS.md)
- [Review Packet](docs/REVIEW_PACKET.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Roadmap](docs/ROADMAP.md)
