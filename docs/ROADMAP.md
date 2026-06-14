# Roadmap

## Phase 1: Engine Foundation

- Pydantic schemas
- SQLite project database
- file ingestion and validation
- deterministic run worker
- stable issue IDs
- reviewer-driven packet export

## Phase 2: Desktop Workflow

- Electron shell
- React findings review UI
- FastAPI sidecar
- project setup, file roles, validation, run status, finding edits, packet export
- mocked React/API project-to-packet workflow coverage

## Phase 3: Training And Regression

- training set creation
- finding labels
- missed finding records
- golden comparison
- regression tests
- per-rule accepted-rate and false-positive usefulness summaries

## Phase 4: Company Readiness

- profile import/export UI
- desktop reference mapping editor
- real-project local smoke profile tuning
- richer diagnostics
- revision comparison UI refinements
- backcheck-required comparison workflow
- packaging scripts
- Windows installer
- signed releases
- auto-update workflow

## Phase 5: Optional Advanced Automation

- optional local/API AI comment rewriting
- built-in PDF preview
- Bluebeam Studio/API integration
- SharePoint/Jira/Planner/Power BI integrations
- CAD/DWG support
- licensing and enterprise governance

All Phase 5 items must remain optional and must not weaken the local deterministic review workflow.
