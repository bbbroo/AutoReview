from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from ng_drawing_qa.errors import ValidationError
from ng_drawing_qa.sample import generate_sample_project
from ng_drawing_qa.schemas import (
    FileRole,
    FindingPatch,
    FindingStatus,
    MissedFindingCreate,
    PacketExportSettings,
    PacketFindingScope,
    PacketMode,
    ProjectCreate,
    TrainingLabel,
    TrainingLabelRequest,
    TrainingSetCreate,
)
from ng_drawing_qa.services.files import infer_file_role, ingest_file
from ng_drawing_qa.services.packet import export_review_packet
from ng_drawing_qa.services.profiles import export_review_profile, import_review_profile
from ng_drawing_qa.services.projects import create_project
from ng_drawing_qa.services.reference_mappings import analyze_project_references, load_reference_mappings, save_reference_mapping
from ng_drawing_qa.services.review import run_project_review
from ng_drawing_qa.services.training import add_missed_finding, compare_against_golden, create_training_set, label_finding
from ng_drawing_qa.services.validation import validate_project_inputs
from ng_drawing_qa.storage.sqlite import AppIndex, ProjectRepository


def _seed_sample_project(tmp_path: Path):
    sample_dir = tmp_path / "sample"
    generate_sample_project(sample_dir)
    app_index = AppIndex(tmp_path / "app.sqlite")
    project = create_project(ProjectCreate(name="Service Test", root_path=tmp_path / "projects"), app_index)
    repo = ProjectRepository(project.database_path)
    files = {
        "sample_natural_gas_drawing_set.pdf": FileRole.DRAWING_SET,
        "drawing_index.csv": FileRole.DRAWING_INDEX,
        "valve_list.csv": FileRole.VALVE_LIST,
        "line_list.csv": FileRole.LINE_LIST,
        "instrument_index.csv": FileRole.INSTRUMENT_INDEX,
        "equipment_list.csv": FileRole.EQUIPMENT_LIST,
    }
    for name, role in files.items():
        ingest_file(repo, project.id, project.root_path, sample_dir / name, role=role)
    return project, repo


def test_infer_file_role_for_common_reference_names():
    assert infer_file_role(Path("valve_list.xlsx")) == FileRole.VALVE_LIST
    assert infer_file_role(Path("drawing_index.csv")) == FileRole.DRAWING_INDEX
    assert infer_file_role(Path("station_ifc.pdf")) == FileRole.DRAWING_SET


def test_project_review_persists_findings_and_exports_packet(tmp_path: Path):
    project, repo = _seed_sample_project(tmp_path)
    validation = validate_project_inputs(repo.list_files(project.id))
    assert not [issue for issue in validation if issue.level == "error"]

    run = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "service-test")
    run_project_review(project.database_path, project.id, run.id, "balanced")

    completed = repo.get_run(run.id)
    findings = repo.list_findings(run.id)
    assert completed is not None
    assert completed.status.value == "completed"
    assert completed.issue_count == len(findings)
    assert findings
    assert findings[0].issue_id.startswith("AR-")
    assert findings[0].original_message == findings[0].edited_message
    assert findings[0].evidence.reason

    assert len(findings) >= 4
    visual_findings = [finding for finding in findings if finding.x1 > finding.x0 and finding.y1 > finding.y0]
    assert visual_findings
    accepted_primary = visual_findings[0]
    accepted_secondary = next(finding for finding in findings if finding.id != accepted_primary.id)
    rejected_finding = next(finding for finding in findings if finding.id not in {accepted_primary.id, accepted_secondary.id})
    backcheck_finding = next(
        finding for finding in findings if finding.id not in {accepted_primary.id, accepted_secondary.id, rejected_finding.id}
    )
    repo.patch_finding(accepted_primary.id, FindingPatch(status=FindingStatus.ACCEPTED, edited_message="Reviewer-approved wording."))
    repo.patch_finding(rejected_finding.id, FindingPatch(status=FindingStatus.REJECTED, reviewer_notes="Rejected in regression test."))
    repo.patch_finding(
        accepted_secondary.id,
        FindingPatch(status=FindingStatus.ACCEPTED, edited_message="Second accepted reviewer wording."),
    )
    reviewed = repo.get_finding(accepted_primary.id)
    assert reviewed is not None
    assert {decision.field_name for decision in reviewed.decision_history} >= {"status", "edited_message"}
    assert any(decision.previous_value == "Draft" and decision.new_value == "Accepted" for decision in reviewed.decision_history)
    assert reviewed.decision_history[0].issue_id == accepted_primary.issue_id
    packet = export_review_packet(
        project.database_path,
        run.id,
        PacketExportSettings(finding_scope=PacketFindingScope.ACCEPTED_ONLY),
    )
    assert packet.finding_count == 2
    assert packet.packet_path.exists()
    with fitz.open(packet.packet_path) as packet_doc:
        packet_text = "\n".join(page.get_text() for page in packet_doc)
        toc = packet_doc.get_toc()
        toc_titles = [item[1] for item in toc]
        front_links = [
            link
            for page_index in range(min(packet_doc.page_count, 4))
            for link in packet_doc[page_index].get_links()
        ]
        drawing_divider_page_num = next(item[2] for item in toc if item[1] == "Marked-Up Drawing Set")
        reference_divider_page_num = next(item[2] for item in toc if item[1] == "Rendered Reference Inputs")
        drawing_label_subjects = []
        for page_index in range(drawing_divider_page_num, reference_divider_page_num - 1):
            annots = list(packet_doc[page_index].annots() or [])
            drawing_label_subjects.extend((annot.info or {}).get("subject", "") for annot in annots)
    assert "Issue Index" in packet_text
    assert "Marked-Up Drawing Set" in packet_text
    assert "Rendered Reference Inputs" in packet_text
    assert "Packet Source Map" in packet_text
    assert "Reviewer-approved wording." in packet_text
    assert accepted_primary.issue_id in packet_text
    assert rejected_finding.issue_id not in packet_text
    assert "Issue Index" in toc_titles
    assert "Marked-Up Drawing Set" in toc_titles
    assert "Rendered Reference Inputs" in toc_titles
    assert "Packet Source Map" in toc_titles
    assert any(link["kind"] == fitz.LINK_GOTO for link in front_links)
    assert f"{accepted_primary.issue_id} - Issue ID Label" in drawing_label_subjects

    repo.patch_finding(backcheck_finding.id, FindingPatch(status=FindingStatus.BACKCHECK_REQUIRED, edited_message="Backcheck-required wording."))
    backcheck_packet = export_review_packet(
        project.database_path,
        run.id,
        PacketExportSettings(packet_mode=PacketMode.BACKCHECK),
    )
    assert backcheck_packet.settings.finding_scope == PacketFindingScope.BACKCHECK
    assert backcheck_packet.finding_count == 1
    debug_settings = PacketExportSettings(packet_mode=PacketMode.FULL_DEBUG, finding_scope=PacketFindingScope.ALL)
    assert debug_settings.include_rejected_findings is True
    assert debug_settings.include_debug_pages is True
    with fitz.open(backcheck_packet.packet_path) as packet_doc:
        backcheck_text = "\n".join(page.get_text() for page in packet_doc)
    assert "Backcheck-required wording." in backcheck_text
    assert "Reviewer-approved wording." not in backcheck_text
    assert rejected_finding.issue_id not in backcheck_text

    manifest = json.loads((completed.output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run.id
    assert manifest["profile"] == "balanced"
    assert manifest["input_files"]
    assert manifest["input_files"][0]["sha256"]
    assert manifest["packet_finding_count"] == 1
    assert manifest["output_packet_path"] == str(backcheck_packet.packet_path)
    assert manifest["packet_export_settings"]["packet_mode"] == "backcheck"
    assert manifest["packet_export_settings"]["finding_scope"] == "backcheck"
    assert manifest["finding_status_counts"]["Accepted"] == 2
    assert manifest["finding_status_counts"]["Rejected"] == 1
    assert manifest["finding_status_counts"]["Backcheck Required"] == 1


def test_reviewer_decision_history_tracks_finding_edits(tmp_path: Path):
    project, repo = _seed_sample_project(tmp_path)
    run = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "decision-history")
    run_project_review(project.database_path, project.id, run.id, "balanced")
    finding = repo.list_findings(run.id)[0]

    updated = repo.patch_finding(
        finding.id,
        FindingPatch(
            status=FindingStatus.NEEDS_REVIEW,
            severity="Critical",
            discipline="QA Verification",
            edited_message="Decision history wording.",
            reviewer_notes="Needs senior reviewer.",
            rfi_candidate=True,
        ),
    )

    fields = {decision.field_name: decision for decision in updated.decision_history}
    assert fields["status"].previous_value == "Draft"
    assert fields["status"].new_value == "Needs Review"
    assert fields["severity"].new_value == "Critical"
    assert fields["discipline"].new_value == "QA Verification"
    assert fields["edited_message"].new_value == "Decision history wording."
    assert fields["reviewer_notes"].new_value == "Needs senior reviewer."
    assert fields["rfi_candidate"].previous_value == "false"
    assert fields["rfi_candidate"].new_value == "true"
    assert all(decision.reviewer == "local_user" for decision in updated.decision_history)


def test_packet_export_requires_completed_run(tmp_path: Path):
    project, repo = _seed_sample_project(tmp_path)
    run = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "queued-export")

    with pytest.raises(ValidationError, match="after a review run completes"):
        export_review_packet(project.database_path, run.id, PacketExportSettings())


def test_fingerprints_and_issue_ids_are_stable_across_repeated_runs(tmp_path: Path):
    project, repo = _seed_sample_project(tmp_path)
    run_one = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "run-one")
    run_project_review(project.database_path, project.id, run_one.id, "balanced")
    first = {finding.fingerprint: finding.issue_id for finding in repo.list_findings(run_one.id)}

    run_two = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "run-two")
    run_project_review(project.database_path, project.id, run_two.id, "balanced")
    second = {finding.fingerprint: finding.issue_id for finding in repo.list_findings(run_two.id)}

    assert first
    assert first == second


def test_validation_reports_user_fixable_file_errors(tmp_path: Path):
    app_index = AppIndex(tmp_path / "app.sqlite")
    project = create_project(ProjectCreate(name="Validation Test", root_path=tmp_path / "projects"), app_index)
    repo = ProjectRepository(project.database_path)

    with pytest.raises(ValidationError, match="could not be found"):
        ingest_file(repo, project.id, project.root_path, tmp_path / "missing.pdf", role=FileRole.DRAWING_SET)

    blank_pdf = tmp_path / "blank.pdf"
    blank_pdf.write_bytes(b"")
    blank = ingest_file(repo, project.id, project.root_path, blank_pdf, role=FileRole.DRAWING_SET)
    issues = validate_project_inputs(repo.list_files(project.id))
    assert any(issue.code == "BLANK_FILE" and issue.file_id == blank.id for issue in issues)

    bad_valves = tmp_path / "valves.csv"
    bad_valves.write_text("description\nmissing tag column\n", encoding="utf-8")
    valves = ingest_file(repo, project.id, project.root_path, bad_valves, role=FileRole.VALVE_LIST)
    issues = validate_project_inputs(repo.list_files(project.id))
    missing_columns = [issue for issue in issues if issue.code == "MISSING_REQUIRED_COLUMNS" and issue.file_id == valves.id]
    assert missing_columns
    assert missing_columns[0].details["missing"] == ["tag"]


def test_reference_analysis_uses_saved_mappings_and_flags_bad_rows(tmp_path: Path):
    app_index = AppIndex(tmp_path / "app.sqlite")
    project = create_project(ProjectCreate(name="Reference Mapping Test", root_path=tmp_path / "projects"), app_index)
    repo = ProjectRepository(project.database_path)

    valves_csv = tmp_path / "custom_valves.csv"
    valves_csv.write_text(
        "Valve ID,Size,Service\n"
        "BV-101,2,Gas\n"
        ",3,Gas\n"
        "BV-101,2,Gas\n"
        "notatag,4,Gas\n"
        "wrong,4,Gas\n"
        "bad,4,Gas\n",
        encoding="utf-8",
    )
    valve_file = ingest_file(repo, project.id, project.root_path, valves_csv, role=FileRole.VALVE_LIST)

    before_mapping = validate_project_inputs(repo.list_files(project.id), project_root=project.root_path)
    assert any(issue.code == "MISSING_REQUIRED_COLUMNS" and issue.file_id == valve_file.id for issue in before_mapping)

    saved = save_reference_mapping(project.database_path, FileRole.VALVE_LIST, {"tag": "Valve ID", "size": "Size", "service": "Service"})
    assert saved.path.exists()
    assert load_reference_mappings(project.root_path)[FileRole.VALVE_LIST]["tag"] == "Valve ID"

    analyses = analyze_project_references(repo.list_files(project.id), project.root_path)
    analysis = next(item for item in analyses if item.file_id == valve_file.id)
    assert analysis.saved_mapping["tag"] == "Valve ID"
    assert analysis.effective_mapping["tag"] == "Valve ID"
    assert analysis.preview_rows[0].key_value == "BV-101"

    codes = {issue.code for issue in analysis.issues}
    assert "MISSING_REQUIRED_COLUMNS" not in codes
    assert {"BLANK_REFERENCE_KEYS", "DUPLICATE_REFERENCE_KEYS", "SUSPICIOUS_REFERENCE_VALUES"} <= codes


def test_training_set_labels_and_golden_regression(tmp_path: Path):
    project, repo = _seed_sample_project(tmp_path)
    run = repo.create_run(project.id, "balanced", project.root_path / "outputs" / "runs" / "training-test")
    run_project_review(project.database_path, project.id, run.id, "balanced")
    findings = repo.list_findings(run.id)
    training_set = create_training_set(
        project.database_path,
        TrainingSetCreate(name="Golden Sample", source_project_id=project.id, source_run_id=run.id, notes="sample"),
    )

    label = label_finding(
        project.database_path,
        training_set.id,
        TrainingLabelRequest(finding_id=findings[0].id, label=TrainingLabel.FALSE_POSITIVE, notes="too noisy", save_as_suppression=True),
    )
    missed = add_missed_finding(
        project.database_path,
        training_set.id,
        MissedFindingCreate(rule_id="VALVE_TAG_RECONCILIATION", sheet_number="P-201", expected_message="Expected missed valve."),
    )
    result = compare_against_golden(project.database_path, training_set.id)

    assert training_set.golden_path is not None
    assert training_set.golden_path.exists()
    assert label.fingerprint == findings[0].fingerprint
    assert missed.rule_id == "VALVE_TAG_RECONCILIATION"
    assert result.expected_count == len(findings)
    assert result.actual_count == len(findings)
    assert result.false_positive_count == 1
    assert result.missed_finding_count == 1
    rules = {row.rule_id: row for row in result.rule_performance}
    assert findings[0].rule_id in rules
    assert rules[findings[0].rule_id].false_positive_count == 1
    assert rules["VALVE_TAG_RECONCILIATION"].missed_finding_count >= 1
    assert sum(row.expected_count for row in result.rule_performance) == len(findings)
    assert sum(row.actual_count for row in result.rule_performance) == len(findings)


def test_profile_export_import(tmp_path: Path):
    project, _ = _seed_sample_project(tmp_path)
    save_reference_mapping(project.database_path, FileRole.VALVE_LIST, {"tag": "Valve Tag"})
    exported = export_review_profile(project.database_path, "balanced")
    imported = import_review_profile(project.database_path, Path(exported["path"]))
    payload = json.loads(Path(exported["path"]).read_text(encoding="utf-8"))

    assert Path(exported["path"]).exists()
    assert payload["reference_mappings"]["valve_list"]["tag"] == "Valve Tag"
    assert imported["profile_name"] == "balanced"
