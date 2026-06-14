# Architecture

AutoReview is a local hybrid desktop system.

## Components

- `apps/desktop`: Electron shell, React UI, TypeScript API client, Fluent-style desktop layout.
- `apps/backend`: FastAPI local sidecar. Owns API routes, project discovery, worker launch, and friendly error boundaries.
- `ng_drawing_qa`: Python review engine, schemas, services, SQLite persistence, deterministic rules, report writers, and packet generation.
- `tests`: Python integration and regression tests.
- `scripts`: Windows development scripts.

## Data Flow

1. Electron starts the FastAPI sidecar on `127.0.0.1`.
2. The UI creates or opens a local project folder.
3. Files are copied into project-local `inputs` folders and recorded in `project.sqlite`.
4. Validation checks paths, file type, PDF readability, searchability, and table columns.
5. A review run is queued in SQLite.
6. The sidecar launches an isolated Python worker process.
7. The worker extracts text/coordinates, loads references, runs deterministic rules, writes support outputs, and persists findings.
8. The reviewer edits and classifies findings in the UI.
9. Packet export rebuilds markups from stored reviewer-approved findings.

The direct-PDF CLI follows the same service path by creating a transient local project in the requested output directory, ingesting the drawing/reference files, creating a persisted run, and calling the same review and packet services.

## Shared Workflow Boundary

The production MVP path is the persisted project workflow: desktop UI, FastAPI sidecar, SQLite project storage, Python worker, CLI direct-PDF runs, finding review, and packet export all operate through `ng_drawing_qa.services.review.run_project_review` and `ng_drawing_qa.services.packet.export_review_packet`.

This keeps rule execution, finding creation, issue IDs, fingerprints, run manifests, packet filtering, edited wording, and support outputs aligned across UI, backend, worker, and CLI entry points.

## Diagnostics

Each persisted run writes `run_manifest.json` under `outputs/runs/{run_id}`. The manifest includes project/run identity, profile, app/engine versions, input file paths and hashes, active rule counts, issue and severity counts, reviewer status counts after packet export, output files, packet path, warnings, and failure messages when available.

## Project Folder

```text
project/
  inputs/
  outputs/runs/{run_id}/
  packets/
  logs/
  debug/
  profiles/
  training/
  project.sqlite
```

## Local-Only Boundary

The MVP does not send files outside the local computer. Optional integrations must be explicitly enabled in future work and must not change deterministic review traceability.
