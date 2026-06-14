from __future__ import annotations

from pathlib import Path

import fitz

from ..schemas import FileRecord, FileRole, ValidationIssue
from .files import validate_file_record
from .reference_mappings import REFERENCE_TABLE_ROLES, analyze_reference_file, load_reference_mappings


def validate_project_inputs(files: list[FileRecord], min_words_per_page: int = 20, project_root: Path | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    saved_mappings = load_reference_mappings(project_root) if project_root else {}
    for record in files:
        issues.extend(validate_file_record(record))
        if not record.local_path.exists():
            continue
        if record.extension == ".pdf":
            issues.extend(validate_pdf(record, min_words_per_page=min_words_per_page))
            if record.role in REFERENCE_TABLE_ROLES:
                issues.extend(analyze_reference_file(record, saved_mappings).issues)
        elif record.extension in {".csv", ".xlsx", ".xlsm"}:
            issues.extend(validate_table_reference(record, saved_mappings=saved_mappings))
        elif record.extension == ".docx":
            issues.append(ValidationIssue(level="warning", code="DOCX_PLACEHOLDER", message="DOCX files are accepted as reference inputs, but direct DOCX rendering is not fully implemented in this MVP.", file_id=record.id, role=record.role))

    drawing_sets = [f for f in files if f.role == FileRole.DRAWING_SET]
    if not drawing_sets:
        issues.append(ValidationIssue(level="error", code="MISSING_DRAWING_SET", message="Select one drawing set PDF before running a review.", role=FileRole.DRAWING_SET))
    elif len(drawing_sets) > 1:
        issues.append(ValidationIssue(level="warning", code="MULTIPLE_DRAWING_SETS", message="Multiple drawing set PDFs are assigned. The first one will be used for this MVP.", role=FileRole.DRAWING_SET))
    return issues


def validate_pdf(record: FileRecord, min_words_per_page: int = 20) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    path = record.local_path
    try:
        doc = fitz.open(path)
    except Exception as exc:
        return [ValidationIssue(level="error", code="PDF_UNREADABLE", message=f"{record.file_name} could not be opened as a PDF: {exc}", file_id=record.id, role=record.role)]
    try:
        if doc.page_count <= 0:
            issues.append(ValidationIssue(level="error", code="PDF_NO_PAGES", message=f"{record.file_name} has no pages.", file_id=record.id, role=record.role))
            return issues
        sample_pages = min(5, doc.page_count)
        word_counts = []
        for i in range(sample_pages):
            try:
                word_counts.append(len(doc[i].get_text("words") or []))
            except Exception:
                word_counts.append(0)
        low_pages = sum(1 for count in word_counts if count < min_words_per_page)
        if low_pages == sample_pages:
            issues.append(ValidationIssue(level="warning", code="LOW_SEARCHABILITY", message=f"The first {sample_pages} page(s) have very little searchable text. Bluebeam OCR may be required for reliable tag checks.", file_id=record.id, role=record.role, details={"sample_word_counts": word_counts}))
        elif low_pages:
            issues.append(ValidationIssue(level="info", code="PARTIAL_LOW_SEARCHABILITY", message=f"{low_pages} of the first {sample_pages} sampled page(s) have low searchable text.", file_id=record.id, role=record.role, details={"sample_word_counts": word_counts}))
    finally:
        doc.close()
    return issues


def validate_table_reference(record: FileRecord, saved_mappings: dict[FileRole, dict[str, str]] | None = None) -> list[ValidationIssue]:
    return analyze_reference_file(record, saved_mappings or {}).issues
