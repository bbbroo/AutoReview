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
4. Validation checks paths, file type, PDF readability, searchability, table columns, reference mappings, blank keys, duplicate keys, and suspicious reference values.
5. A review run is queued in SQLite.
6. The sidecar launches an isolated Python worker process.
7. The worker extracts text/coordinates, loads references, runs deterministic rules with profile-controlled evidence thresholds, writes support outputs, and persists findings.
8. The reviewer edits and classifies findings in the UI.
9. Packet export rebuilds markups from stored reviewer-approved findings.

The direct-PDF CLI follows the same service path by creating a transient local project in the requested output directory, ingesting the drawing/reference files, creating a persisted run, and calling the same review and packet services.

Reference CSV/XLSX files are analyzed before a run through the same local API. The UI shows parsed headers, preview rows, inferred/saved/effective mappings, and validation messages, then saves reusable role-based mappings under `profiles/reference_mappings.json`.

## Shared Workflow Boundary

The production MVP path is the persisted project workflow: desktop UI, FastAPI sidecar, SQLite project storage, Python worker, CLI direct-PDF runs, finding review, and packet export all operate through `ng_drawing_qa.services.review.run_project_review` and `ng_drawing_qa.services.packet.export_review_packet`.

This keeps rule execution, finding creation, issue IDs, fingerprints, run manifests, packet filtering, edited wording, and support outputs aligned across UI, backend, worker, and CLI entry points. The CLI is intentionally a thin persisted-project wrapper, not a separate direct-PDF review engine.

## Diagnostics

Each persisted run writes `run_manifest.json` under `outputs/runs/{run_id}`. The manifest includes project/run identity, profile, app/engine versions, input file paths and hashes, active rule counts, issue and severity counts, deterministic finding fingerprints, a compact finding trace, reviewer status counts after packet export, output files, packet path, warnings, and failure messages when available.

Each completed review run also writes `finding_traceability.csv` beside `issue_log.csv`. This CSV is the low-friction audit surface for comparing UI/backend/worker/CLI runs because it records issue ID, fingerprint, rule, status, severity, sheet/page, found text, confidence, and source for each persisted finding.

Finding reviewer changes are stored in SQLite `finding_decisions`. Each changed field records the finding ID, issue ID, run/project IDs, previous value, new value, timestamp, and local reviewer marker. The MVP is local single-user, so the reviewer marker is `local_user` until a future team workflow adds identity.

False-positive reduction is handled inside the deterministic rule layer and profile settings, not by a separate UI/backend path. Rules can suppress ambiguous tag hits, downgrade reference-only mismatches when page searchability is weak, require readable title-block evidence before field-level comments, and require explicit regulator context before checklist prompts. The same confidence/severity result is persisted, shown in the UI, exported to trace CSVs, and used by packet export.

Run comparison reports new, resolved, repeated, carryover, status-changed, severity-changed, message-changed, and backcheck-required findings so reviewers can check whether prior revision comments were resolved.

## Project Folder

```text
project/
  inputs/
  outputs/runs/{run_id}/
  packets/
  logs/
  debug/
  profiles/
    reference_mappings.json
  training/
  project.sqlite
```

## Local-Only Boundary

The MVP does not send files outside the local computer. Optional integrations must be explicitly enabled in future work and must not change deterministic review traceability.
