from __future__ import annotations

from pathlib import Path

import fitz

from ..annotations import annotate_pdf
from ..config import load_config
from ..errors import MissingInputError, ValidationError
from ..models import Issue
from ..review_packet import build_single_review_packet
from ..schemas import (
    FileRecord,
    FileRole,
    FindingRecord,
    FindingStatus,
    PacketExportRecord,
    PacketExportSettings,
    PacketFindingScope,
)
from ..storage.sqlite import ProjectRepository, new_id, now_iso
from .review import REFERENCE_ROLE_TO_CONFIG_KEY, _reference_overrides, load_project_references


def _finding_selected(finding: FindingRecord, settings: PacketExportSettings) -> bool:
    if settings.finding_scope == PacketFindingScope.ALL:
        return True
    if settings.finding_scope == PacketFindingScope.ACCEPTED_ONLY:
        return finding.status == FindingStatus.ACCEPTED
    if settings.finding_scope == PacketFindingScope.ACCEPTED_AND_NEEDS_REVIEW:
        return finding.status in {
            FindingStatus.ACCEPTED,
            FindingStatus.NEEDS_REVIEW,
            FindingStatus.NEEDS_MORE_INFORMATION,
            FindingStatus.RFI_CANDIDATE,
            FindingStatus.BACKCHECK_REQUIRED,
        }
    if settings.finding_scope == PacketFindingScope.ALL_NON_REJECTED:
        return finding.status != FindingStatus.REJECTED
    return False


def _issue_from_finding(finding: FindingRecord) -> Issue:
    return Issue(
        issue_id=finding.issue_id,
        rule_id=finding.rule_id,
        subject=finding.subject,
        message=finding.edited_message or finding.original_message,
        severity=finding.severity.value,
        discipline=finding.discipline,
        confidence=finding.confidence,
        status=finding.status.value,
        page_number=finding.page_number,
        output_pdf_page_number=finding.output_pdf_page_number,
        sheet_number=finding.sheet_number,
        found_text=finding.found_text,
        context=finding.context,
        x0=finding.x0,
        y0=finding.y0,
        x1=finding.x1,
        y1=finding.y1,
        owner=finding.owner,
        response=finding.reviewer_notes,
        source=finding.source,
        rfi_candidate="Yes" if finding.rfi_candidate else "No",
    )


def _drawing_set(files: list[FileRecord]) -> FileRecord | None:
    return next((file for file in files if file.role == FileRole.DRAWING_SET), None)


def _supplemental_reference_files(files: list[FileRecord]) -> list[Path]:
    out: list[Path] = []
    for file in files:
        if file.role == FileRole.DRAWING_SET:
            continue
        if file.extension in {".pdf", ".docx", ".txt"}:
            out.append(file.local_path)
    return out


def export_review_packet(
    project_db_path: Path,
    run_id: str,
    settings: PacketExportSettings | None = None,
) -> PacketExportRecord:
    settings = settings or PacketExportSettings()
    repo = ProjectRepository(project_db_path)
    run = repo.get_run(run_id)
    if run is None:
        raise MissingInputError(f"Run not found: {run_id}")
    project = repo.get_project(run.project_id)
    if project is None:
        raise MissingInputError(f"Project not found: {run.project_id}")

    files = repo.list_files(project.id)
    drawing = _drawing_set(files)
    if drawing is None:
        raise MissingInputError("No drawing set PDF is assigned to this project.")
    if not drawing.local_path.exists():
        raise MissingInputError(f"Drawing set PDF could not be found: {drawing.local_path}")

    findings = [finding for finding in repo.list_findings(run_id) if _finding_selected(finding, settings)]
    issues = [_issue_from_finding(finding) for finding in findings]

    config = load_config(profile=run.profile)
    config.setdefault("outputs", {})["dry_run"] = False
    config.setdefault("outputs", {})["annotate_pdf"] = True
    config.setdefault("outputs", {})["insert_summary_page"] = False
    config.setdefault("outputs", {})["single_review_packet_pdf"] = True
    config.setdefault("outputs", {})["single_review_packet_name"] = settings.packet_name

    overrides = _reference_overrides(files)
    refs = load_project_references(config, overrides)

    packet_dir = project.root_path / "packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    packet_path = packet_dir / settings.packet_name
    if packet_path.exists():
        packet_path = packet_dir / f"{packet_path.stem}_{now_iso().replace(':', '')}{packet_path.suffix}"

    doc = fitz.open(drawing.local_path)
    try:
        annotate_pdf(doc, issues, config)
        marked_path = run.output_dir / f"{Path(drawing.file_name).stem}_reviewed_marked_up.pdf"
        marked_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(marked_path, garbage=4, deflate=True)
        supplemental = _supplemental_reference_files(files) if settings.include_reference_inputs else []
        build_single_review_packet(doc, issues, refs if settings.include_reference_inputs else {}, packet_path, config, supplemental_reference_files=supplemental)
    except Exception as exc:
        raise ValidationError(f"Packet export failed: {exc}") from exc
    finally:
        doc.close()

    record = PacketExportRecord(
        id=new_id("packet"),
        run_id=run.id,
        project_id=project.id,
        packet_path=packet_path,
        settings=settings,
        finding_count=len(issues),
        created_at=now_iso(),
    )
    return repo.add_packet_export(record)
