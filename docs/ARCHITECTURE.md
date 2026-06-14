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
