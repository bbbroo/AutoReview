from __future__ import annotations

from pathlib import Path

import fitz

from ..reference import pick_column, read_table
from ..schemas import FileRecord, FileRole, ValidationIssue
from .files import validate_file_record


STRUCTURED_COLUMN_CANDIDATES: dict[FileRole, dict[str, list[str]]] = {
    FileRole.DRAWING_INDEX: {
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "dwg_no", "drawing_no"],
    },
    FileRole.VALVE_LIST: {"tag": ["tag", "valve_tag", "valve", "tag_number", "item_tag"]},
    FileRole.LINE_LIST: {"tag": ["line_number", "line_no", "line", "tag", "line_tag"]},
    FileRole.INSTRUMENT_INDEX: {"tag": ["tag", "instrument_tag", "instrument", "tag_number", "loop_tag"]},
    FileRole.EQUIPMENT_LIST: {"tag": ["tag", "equipment_tag", "item_tag"]},
    FileRole.ALIAS_TABLE: {"alias": ["old", "alias", "from", "source", "drawing_tag"], "canonical": ["new", "canonical", "to", "target", "reference_tag"]},
    FileRole.IGNORE_PATTERNS: {"pattern": ["pattern", "regex", "ignore"]},
}


def validate_project_inputs(files: list[FileRecord], min_words_per_page: int = 20) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for record in files:
        issues.extend(validate_file_record(record))
        if not record.local_path.exists():
            continue
        if record.extension == ".pdf":
            issues.extend(validate_pdf(record, min_words_per_page=min_words_per_page))
            if record.role in STRUCTURED_COLUMN_CANDIDATES:
                issues.append(ValidationIssue(level="warning", code="PDF_REFERENCE_TEXT_ONLY", message=f"{record.file_name} is assigned to {record.role.value}, but structured reconciliation currently uses CSV/XLSX columns. This PDF will be preserved as reference evidence.", file_id=record.id, role=record.role))
        elif record.extension in {".csv", ".xlsx", ".xlsm"}:
            issues.extend(validate_table_reference(record))
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


def validate_table_reference(record: FileRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    path = Path(record.local_path)
    try:
        headers, rows = read_table(path)
    except Exception as exc:
        return [ValidationIssue(level="error", code="TABLE_UNREADABLE", message=f"{record.file_name} could not be read as a table: {exc}", file_id=record.id, role=record.role)]
    if not headers:
        issues.append(ValidationIssue(level="error", code="TABLE_NO_HEADERS", message=f"{record.file_name} does not have a readable header row.", file_id=record.id, role=record.role))
        return issues
    if not rows:
        issues.append(ValidationIssue(level="warning", code="TABLE_NO_ROWS", message=f"{record.file_name} has headers but no data rows.", file_id=record.id, role=record.role))

    required = STRUCTURED_COLUMN_CANDIDATES.get(record.role, {})
    missing = []
    for field, candidates in required.items():
        if not pick_column(headers, candidates):
            missing.append(field)
    if missing:
        issues.append(ValidationIssue(
            level="error",
            code="MISSING_REQUIRED_COLUMNS",
            message=f"{record.file_name} is missing required mapped column(s): {', '.join(missing)}.",
            file_id=record.id,
            role=record.role,
            details={"headers": headers, "missing": missing},
        ))
    return issues
