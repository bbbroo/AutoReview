from __future__ import annotations

import json
from pathlib import Path

from ..errors import MissingInputError, ValidationError
from ..schemas import (
    MissedFindingCreate,
    MissedFindingRecord,
    RegressionResult,
    RulePerformanceSummary,
    TrainingLabel,
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


def _rule_for_fingerprint(
    fingerprint: str,
    expected: dict[str, dict],
    actual: dict,
    labels: list[TrainingLabelRecord],
) -> str:
    if fingerprint in actual:
        return str(actual[fingerprint].rule_id)
    if fingerprint in expected:
        return str(expected[fingerprint].get("rule_id") or "UNKNOWN_RULE")
    for label in labels:
        if label.fingerprint == fingerprint and label.finding_id:
            return "UNKNOWN_RULE"
    return "UNKNOWN_RULE"


def _rule_performance_summary(
    expected: dict[str, dict],
    actual: dict,
    missing: list[str],
    new: list[str],
    changed: list[dict],
    labels: list[TrainingLabelRecord],
    missed_findings: list[MissedFindingRecord],
) -> list[RulePerformanceSummary]:
    by_rule: dict[str, dict[str, int]] = {}

    def bucket(rule_id: str) -> dict[str, int]:
        if rule_id not in by_rule:
            by_rule[rule_id] = {
                "expected_count": 0,
                "actual_count": 0,
                "matched_count": 0,
                "missing_count": 0,
                "new_count": 0,
                "changed_count": 0,
                "correct_count": 0,
                "false_positive_count": 0,
                "needs_better_wording_count": 0,
                "rule_needs_tuning_count": 0,
                "missed_finding_count": 0,
                "accepted_count": 0,
                "accepted_rate": 0.0,
            }
        return by_rule[rule_id]

    for row in expected.values():
        bucket(str(row.get("rule_id") or "UNKNOWN_RULE"))["expected_count"] += 1
    for finding in actual.values():
        counts = bucket(str(finding.rule_id))
        counts["actual_count"] += 1
        if finding.status.value == "Accepted":
            counts["accepted_count"] += 1
    for fingerprint in sorted(set(expected) & set(actual)):
        bucket(_rule_for_fingerprint(fingerprint, expected, actual, labels))["matched_count"] += 1
    for fingerprint in missing:
        bucket(_rule_for_fingerprint(fingerprint, expected, actual, labels))["missing_count"] += 1
    for fingerprint in new:
        bucket(_rule_for_fingerprint(fingerprint, expected, actual, labels))["new_count"] += 1
    for item in changed:
        bucket(_rule_for_fingerprint(str(item.get("fingerprint", "")), expected, actual, labels))["changed_count"] += 1

    for label in labels:
        rule_id = _rule_for_fingerprint(label.fingerprint, expected, actual, labels)
        if label.label == TrainingLabel.CORRECT:
            bucket(rule_id)["correct_count"] += 1
        elif label.label == TrainingLabel.FALSE_POSITIVE:
            bucket(rule_id)["false_positive_count"] += 1
        elif label.label == TrainingLabel.NEEDS_BETTER_WORDING:
            bucket(rule_id)["needs_better_wording_count"] += 1
        elif label.label == TrainingLabel.RULE_NEEDS_TUNING:
            bucket(rule_id)["rule_needs_tuning_count"] += 1
        elif label.label == TrainingLabel.MISSED_ISSUE:
            bucket(rule_id)["missed_finding_count"] += 1

    for missed in missed_findings:
        bucket(missed.rule_id)["missed_finding_count"] += 1

    summaries: list[RulePerformanceSummary] = []
    for rule_id, counts in sorted(by_rule.items(), key=lambda item: item[0]):
        actual_count = counts.get("actual_count", 0)
        counts["accepted_rate"] = round(counts.get("accepted_count", 0) / actual_count, 3) if actual_count else 0.0
        summaries.append(RulePerformanceSummary(rule_id=rule_id, **counts))
    return summaries


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
    rule_performance = _rule_performance_summary(expected, actual, missing, new, changed, labels, missed)
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
        rule_performance=rule_performance,
    )
