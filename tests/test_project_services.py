from __future__ import annotations

from pathlib import Path

from ng_drawing_qa.sample import generate_sample_project
from ng_drawing_qa.schemas import (
    FileRole,
    FindingPatch,
    FindingStatus,
    PacketExportSettings,
    PacketFindingScope,
    ProjectCreate,
)
from ng_drawing_qa.services.files import infer_file_role, ingest_file
from ng_drawing_qa.services.packet import export_review_packet
from ng_drawing_qa.services.projects import create_project
from ng_drawing_qa.services.review import run_project_review
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

    repo.patch_finding(findings[0].id, FindingPatch(status=FindingStatus.ACCEPTED, edited_message="Reviewer-approved wording."))
    packet = export_review_packet(
        project.database_path,
        run.id,
        PacketExportSettings(finding_scope=PacketFindingScope.ACCEPTED_ONLY),
    )
    assert packet.finding_count == 1
    assert packet.packet_path.exists()
