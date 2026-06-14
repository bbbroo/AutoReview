from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ng_drawing_qa.config import load_config
from ng_drawing_qa.errors import AutoReviewError
from ng_drawing_qa.rules.registry import get_rule_metadata
from ng_drawing_qa.schemas import (
    FileIngestRequest,
    FileRecord,
    FileRole,
    FindingPatch,
    FindingRecord,
    MissedFindingCreate,
    MissedFindingRecord,
    PacketExportRecord,
    PacketExportSettings,
    ProjectCreate,
    ProjectRecord,
    ProgressEvent,
    RegressionResult,
    RunCreate,
    RunRecord,
    TrainingLabelRecord,
    TrainingLabelRequest,
    TrainingSetCreate,
    TrainingSetRecord,
    ValidationIssue,
)
from ng_drawing_qa.services.files import ingest_file
from ng_drawing_qa.services.packet import export_review_packet
from ng_drawing_qa.services.projects import create_project, open_project
from ng_drawing_qa.services.training import add_missed_finding, compare_against_golden, create_training_set, label_finding
from ng_drawing_qa.services.validation import validate_project_inputs
from ng_drawing_qa.storage.sqlite import AppIndex, ProjectRepository


class ProjectOpenRequest(BaseModel):
    root_path: Path


class FileRolePatch(BaseModel):
    role: FileRole


class RunWithProgress(BaseModel):
    run: RunRecord
    progress: list[ProgressEvent]


class RunComparisonSummary(BaseModel):
    base_run_id: str
    compare_run_id: str
    new_issue_ids: list[str]
    resolved_issue_ids: list[str]
    repeated_issue_ids: list[str]
    changed: list[dict[str, Any]]


class RegressionRunRequest(BaseModel):
    run_id: str | None = None


app = FastAPI(title="AutoReview Local Sidecar", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://autoreview"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX = AppIndex()


@app.exception_handler(AutoReviewError)
async def autoreview_error_handler(_, exc: AutoReviewError):
    return JSONResponse(status_code=400, content={"detail": {"code": exc.code, "message": exc.message, "details": exc.details}})


def _project_or_404(project_id: str) -> ProjectRecord:
    project = INDEX.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


def _repo(project: ProjectRecord) -> ProjectRepository:
    return ProjectRepository(project.database_path)


def _find_run(run_id: str) -> tuple[ProjectRecord, ProjectRepository, RunRecord]:
    for project in INDEX.list_projects():
        repo = _repo(project)
        run = repo.get_run(run_id)
        if run is not None:
            return project, repo, run
    raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")


def _find_finding(finding_id: str) -> tuple[ProjectRecord, ProjectRepository, FindingRecord]:
    for project in INDEX.list_projects():
        repo = _repo(project)
        finding = repo.get_finding(finding_id)
        if finding is not None:
            return project, repo, finding
    raise HTTPException(status_code=404, detail=f"Finding not found: {finding_id}")


def _find_training_set(training_set_id: str) -> tuple[ProjectRecord, ProjectRepository, TrainingSetRecord]:
    for project in INDEX.list_projects():
        repo = _repo(project)
        training_set = repo.get_training_set(training_set_id)
        if training_set is not None:
            return project, repo, training_set
    raise HTTPException(status_code=404, detail=f"Training set not found: {training_set_id}")


def _spawn_review_worker(project: ProjectRecord, run: RunRecord) -> None:
    logs_dir = project.root_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{run.id}.worker.log"
    stderr_path = logs_dir / f"{run.id}.worker.err.log"
    args = [
        sys.executable,
        "-m",
        "apps.backend.autoreview_backend.worker",
        "run",
        "--project-db",
        str(project.database_path),
        "--project-id",
        project.id,
        "--run-id",
        run.id,
        "--profile",
        run.profile,
    ]
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")
    try:
        subprocess.Popen(args, cwd=Path.cwd(), stdout=stdout, stderr=stderr)
    finally:
        stdout.close()
        stderr.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-only"}


@app.get("/rules")
def rules():
    return [item.model_dump(mode="json") for item in get_rule_metadata()]


@app.get("/profiles")
def profiles() -> dict[str, Any]:
    cfg = load_config()
    return cfg.get("profiles", {})


@app.post("/projects", response_model=ProjectRecord)
def create_project_route(request: ProjectCreate) -> ProjectRecord:
    return create_project(request, INDEX)


@app.post("/projects/open", response_model=ProjectRecord)
def open_project_route(request: ProjectOpenRequest) -> ProjectRecord:
    return open_project(request.root_path, INDEX)


@app.get("/projects", response_model=list[ProjectRecord])
def list_projects() -> list[ProjectRecord]:
    return INDEX.list_projects()


@app.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str) -> ProjectRecord:
    return _project_or_404(project_id)


@app.post("/projects/{project_id}/files/ingest", response_model=list[FileRecord])
def ingest_files(project_id: str, request: FileIngestRequest) -> list[FileRecord]:
    project = _project_or_404(project_id)
    repo = _repo(project)
    return [
        ingest_file(repo, project.id, project.root_path, path, role=request.role, copy_into_project=request.copy_into_project)
        for path in request.paths
    ]


@app.get("/projects/{project_id}/files", response_model=list[FileRecord])
def list_files(project_id: str) -> list[FileRecord]:
    project = _project_or_404(project_id)
    return _repo(project).list_files(project.id)


@app.patch("/projects/{project_id}/files/{file_id}", response_model=FileRecord)
def update_file_role(project_id: str, file_id: str, patch: FileRolePatch) -> FileRecord:
    project = _project_or_404(project_id)
    return _repo(project).update_file_role(file_id, patch.role)


@app.patch("/files/{file_id}", response_model=FileRecord)
def update_file_role_global(file_id: str, patch: FileRolePatch) -> FileRecord:
    _, repo, _ = _find_file(file_id)
    return repo.update_file_role(file_id, patch.role)


def _find_file(file_id: str):
    for project in INDEX.list_projects():
        repo = _repo(project)
        file = repo.get_file(file_id)
        if file is not None:
            return project, repo, file
    raise HTTPException(status_code=404, detail=f"File not found: {file_id}")


@app.post("/projects/{project_id}/validate", response_model=list[ValidationIssue])
def validate_project(project_id: str) -> list[ValidationIssue]:
    project = _project_or_404(project_id)
    repo = _repo(project)
    return validate_project_inputs(repo.list_files(project.id))


@app.post("/projects/{project_id}/runs", response_model=RunRecord)
def create_run(project_id: str, request: RunCreate) -> RunRecord:
    project = _project_or_404(project_id)
    repo = _repo(project)
    run = repo.create_run(project.id, request.profile, project.root_path / "outputs" / "runs" / "queued")
    run = repo.update_run(run.id, output_dir=project.root_path / "outputs" / "runs" / run.id)
    _spawn_review_worker(project, run)
    return run


@app.get("/runs/{run_id}", response_model=RunWithProgress)
def get_run(run_id: str) -> RunWithProgress:
    _, repo, run = _find_run(run_id)
    return RunWithProgress(run=run, progress=repo.list_progress(run.id))


@app.get("/runs/{run_id}/findings", response_model=list[FindingRecord])
def get_findings(run_id: str) -> list[FindingRecord]:
    _, repo, run = _find_run(run_id)
    return repo.list_findings(run.id)


@app.patch("/findings/{finding_id}", response_model=FindingRecord)
def patch_finding(finding_id: str, patch: FindingPatch) -> FindingRecord:
    _, repo, _ = _find_finding(finding_id)
    return repo.patch_finding(finding_id, patch)


@app.post("/runs/{run_id}/export-packet", response_model=PacketExportRecord)
def export_packet(run_id: str, settings: PacketExportSettings | None = None) -> PacketExportRecord:
    project, _, _ = _find_run(run_id)
    return export_review_packet(project.database_path, run_id, settings or PacketExportSettings())


@app.get("/projects/{project_id}/history", response_model=list[RunRecord])
def project_history(project_id: str) -> list[RunRecord]:
    project = _project_or_404(project_id)
    return _repo(project).list_runs(project.id)


@app.get("/runs/{base_run_id}/compare/{compare_run_id}", response_model=RunComparisonSummary)
def compare_runs(base_run_id: str, compare_run_id: str) -> RunComparisonSummary:
    _, base_repo, base_run = _find_run(base_run_id)
    _, compare_repo, compare_run = _find_run(compare_run_id)
    base_findings = {f.fingerprint: f for f in base_repo.list_findings(base_run.id)}
    compare_findings = {f.fingerprint: f for f in compare_repo.list_findings(compare_run.id)}
    new = [f.issue_id for key, f in compare_findings.items() if key not in base_findings]
    resolved = [f.issue_id for key, f in base_findings.items() if key not in compare_findings]
    repeated = [compare_findings[key].issue_id for key in sorted(set(base_findings) & set(compare_findings))]
    changed: list[dict[str, Any]] = []
    for key in sorted(set(base_findings) & set(compare_findings)):
        before = base_findings[key]
        after = compare_findings[key]
        diffs = {}
        for field in ["severity", "edited_message", "status", "confidence"]:
            if getattr(before, field) != getattr(after, field):
                diffs[field] = {"before": getattr(before, field), "after": getattr(after, field)}
        if diffs:
            changed.append({"issue_id": after.issue_id, "fingerprint": key, "changes": diffs})
    return RunComparisonSummary(
        base_run_id=base_run_id,
        compare_run_id=compare_run_id,
        new_issue_ids=new,
        resolved_issue_ids=resolved,
        repeated_issue_ids=repeated,
        changed=changed,
    )


@app.post("/projects/{project_id}/training-sets", response_model=TrainingSetRecord)
def create_training_set_route(project_id: str, request: TrainingSetCreate) -> TrainingSetRecord:
    project = _project_or_404(project_id)
    normalized = TrainingSetCreate(
        name=request.name,
        source_project_id=project.id,
        source_run_id=request.source_run_id,
        notes=request.notes,
    )
    return create_training_set(project.database_path, normalized)


@app.get("/projects/{project_id}/training-sets", response_model=list[TrainingSetRecord])
def list_training_sets(project_id: str) -> list[TrainingSetRecord]:
    project = _project_or_404(project_id)
    return _repo(project).list_training_sets(project.id)


@app.post("/training-sets/{training_set_id}/labels", response_model=TrainingLabelRecord)
def label_training_finding(training_set_id: str, request: TrainingLabelRequest) -> TrainingLabelRecord:
    project, _, _ = _find_training_set(training_set_id)
    return label_finding(project.database_path, training_set_id, request)


@app.post("/training-sets/{training_set_id}/missed-findings", response_model=MissedFindingRecord)
def add_training_missed_finding(training_set_id: str, request: MissedFindingCreate) -> MissedFindingRecord:
    project, _, _ = _find_training_set(training_set_id)
    return add_missed_finding(project.database_path, training_set_id, request)


@app.post("/training-sets/{training_set_id}/regression", response_model=RegressionResult)
def run_training_regression(training_set_id: str, request: RegressionRunRequest | None = None) -> RegressionResult:
    project, _, _ = _find_training_set(training_set_id)
    return compare_against_golden(project.database_path, training_set_id, request.run_id if request else None)


def run() -> None:
    import uvicorn

    uvicorn.run("apps.backend.autoreview_backend.main:app", host="127.0.0.1", port=8765, reload=False)
