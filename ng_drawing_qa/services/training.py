from __future__ import annotations

import json
from pathlib import Path

from ..errors import MissingInputError, ValidationError
from ..schemas import (
    MissedFindingCreate,
    MissedFindingRecord,
    RegressionResult,
    TrainingLabelRecord,
    TrainingLabelRequest,
    TrainingSetCreate,
    TrainingSetRecord,
)
from ..storage.sqlite import ProjectRepository, new_id, now_iso


def _golden_rows(repo: ProjectRepository, run_id: str) -> list[dict]:
    rows = []
    for finding in repo.list_findings(run_id):
        rows.append({
            "fingerprint": finding.fingerprint,
            "issue_id": finding.issue_id,
            "rule_id": finding.rule_id,
            "severity": finding.severity.value,
            "status": finding.status.value,
            "subject": finding.subject,
            "message": finding.edited_message,
            "sheet_number": finding.sheet_number,
            "found_text": finding.found_text,
        })
    return rows


def create_training_set(project_db_path: Path, request: TrainingSetCreate) -> TrainingSetRecord:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project(request.source_project_id)
    if project is None:
        raise MissingInputError(f"Project not found: {request.source_project_id}")
    if request.source_run_id and repo.get_run(request.source_run_id) is None:
        raise MissingInputError(f"Run not found: {request.source_run_id}")

    training_id = new_id("training")
    training_dir = project.root_path / "training" / training_id
    training_dir.mkdir(parents=True, exist_ok=True)
    golden_path = training_dir / "golden_findings.json"
    golden = _golden_rows(repo, request.source_run_id) if request.source_run_id else []
    golden_path.write_text(json.dumps({"source_run_id": request.source_run_id, "findings": golden}, indent=2), encoding="utf-8")

    record = TrainingSetRecord(
        id=training_id,
        project_id=project.id,
        source_run_id=request.source_run_id,
        name=request.name,
        notes=request.notes,
        golden_path=golden_path,
        created_at=now_iso(),
    )
    return repo.create_training_set(record)


def label_finding(project_db_path: Path, training_set_id: str, request: TrainingLabelRequest) -> TrainingLabelRecord:
    repo = ProjectRepository(project_db_path)
    training_set = repo.get_training_set(training_set_id)
    if training_set is None:
        raise MissingInputError(f"Training set not found: {training_set_id}")
    finding = repo.get_finding(request.finding_id)
    if finding is None:
        raise MissingInputError(f"Finding not found: {request.finding_id}")
    record = TrainingLabelRecord(
        id=new_id("label"),
        training_set_id=training_set_id,
        finding_id=finding.id,
        fingerprint=finding.fingerprint,
        label=request.label,
        notes=request.notes,
        save_as_suppression=request.save_as_suppression,
        created_at=now_iso(),
    )
    return repo.add_training_label(record)


def add_missed_finding(project_db_path: Path, training_set_id: str, request: MissedFindingCreate) -> MissedFindingRecord:
    repo = ProjectRepository(project_db_path)
    if repo.get_training_set(training_set_id) is None:
        raise MissingInputError(f"Training set not found: {training_set_id}")
    record = MissedFindingRecord(
        id=new_id("missed"),
        training_set_id=training_set_id,
        rule_id=request.rule_id,
        sheet_number=request.sheet_number,
        expected_message=request.expected_message,
        severity=request.severity,
        notes=request.notes,
        created_at=now_iso(),
    )
    return repo.add_missed_finding(record)


def compare_against_golden(project_db_path: Path, training_set_id: str, run_id: str | None = None) -> RegressionResult:
    repo = ProjectRepository(project_db_path)
    training_set = repo.get_training_set(training_set_id)
    if training_set is None:
        raise MissingInputError(f"Training set not found: {training_set_id}")
    source_run_id = run_id or training_set.source_run_id
    if not source_run_id:
        raise ValidationError("Training set does not have a source run to compare.")
    if repo.get_run(source_run_id) is None:
        raise MissingInputError(f"Run not found: {source_run_id}")

    if not training_set.golden_path or not training_set.golden_path.exists():
        raise MissingInputError("Golden findings file is missing for this training set.")
    golden_doc = json.loads(training_set.golden_path.read_text(encoding="utf-8"))
    expected = {row["fingerprint"]: row for row in golden_doc.get("findings", [])}
    actual_findings = repo.list_findings(source_run_id)
    actual = {finding.fingerprint: finding for finding in actual_findings}

    missing = sorted(set(expected) - set(actual))
    new = sorted(set(actual) - set(expected))
    changed = []
    for fingerprint in sorted(set(expected) & set(actual)):
        before = expected[fingerprint]
        after = actual[fingerprint]
        diffs = {}
        if before.get("severity") != after.severity.value:
            diffs["severity"] = {"expected": before.get("severity"), "actual": after.severity.value}
        if before.get("message") != after.edited_message:
            diffs["message"] = {"expected": before.get("message"), "actual": after.edited_message}
        if diffs:
            changed.append({"fingerprint": fingerprint, "issue_id": after.issue_id, "changes": diffs})

    labels = repo.list_training_labels(training_set_id)
    missed = repo.list_missed_findings(training_set_id)
    false_positive_count = sum(1 for label in labels if label.label.value == "false_positive")
    return RegressionResult(
        training_set_id=training_set_id,
        source_run_id=source_run_id,
        expected_count=len(expected),
        actual_count=len(actual),
        missing_fingerprints=missing,
        new_fingerprints=new,
        changed=changed,
        false_positive_count=false_positive_count,
        missed_finding_count=len(missed),
    )
