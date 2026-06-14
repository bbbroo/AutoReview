from __future__ import annotations

from collections import Counter
import json
import re
from pathlib import Path
from typing import Any

from ..errors import MissingInputError
from ..reference import normalize_value, pick_column, read_table
from ..schemas import (
    FileRecord,
    FileRole,
    ReferenceAnalysis,
    ReferenceMappingRecord,
    ReferencePreviewRow,
    ValidationIssue,
)
from ..storage.sqlite import ProjectRepository, now_iso


REFERENCE_MAPPING_FILE = "reference_mappings.json"

ROLE_COLUMN_CANDIDATES: dict[FileRole, dict[str, list[str]]] = {
    FileRole.DRAWING_INDEX: {
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no", "dwg_no", "dwg", "sheet_no"],
        "sheet_title": ["sheet_title", "title", "drawing_title", "sheet_name", "description"],
        "revision": ["revision", "rev", "current_rev"],
        "issue_date": ["date", "issue_date", "issued", "ifc_date"],
        "status": ["status", "issue_status", "drawing_status"],
    },
    FileRole.DRAWING_REGISTER: {
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no", "dwg_no", "dwg", "sheet_no"],
        "sheet_title": ["sheet_title", "title", "drawing_title", "sheet_name", "description"],
        "revision": ["revision", "rev", "current_rev"],
        "issue_date": ["date", "issue_date", "issued", "ifc_date"],
        "status": ["status", "issue_status", "drawing_status"],
    },
    FileRole.VALVE_LIST: {
        "tag": ["tag", "valve_tag", "valve", "valve_no", "tag_number", "item_tag"],
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no"],
        "size": ["size", "nominal_size", "nps", "diameter"],
        "type": ["type", "valve_type", "valve_style"],
        "service": ["service", "description", "line_service"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.LINE_LIST: {
        "tag": ["line_number", "line_no", "line", "line_tag", "tag", "pipeline"],
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no"],
        "size": ["size", "nominal_size", "nps", "diameter"],
        "service": ["service", "line_service", "fluid"],
        "maop": ["maop", "maop_psig", "maop_psi", "max_operating_pressure"],
        "design_pressure": ["design_pressure", "design_pressure_psig", "design_psig"],
        "test_pressure": ["test_pressure", "test_pressure_psig", "hydrotest_pressure"],
        "material": ["material", "pipe_material"],
        "spec": ["spec", "pipe_spec", "class", "specification"],
        "coating": ["coating", "coating_spec", "cp_coating"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.INSTRUMENT_INDEX: {
        "tag": ["tag", "instrument_tag", "instrument", "instrument_no", "tag_number", "loop_tag"],
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no"],
        "type": ["type", "instrument_type"],
        "service": ["service", "description"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.EQUIPMENT_LIST: {
        "tag": ["tag", "equipment_tag", "equipment", "equipment_no", "item_tag"],
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no"],
        "type": ["type", "equipment_type"],
        "service": ["service", "description"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.SPEC_LIST: {
        "spec": ["spec", "specification", "pipe_spec", "class", "material_spec"],
        "material": ["material", "pipe_material"],
        "coating": ["coating", "coating_spec"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.TIE_IN_LIST: {
        "tag": ["tie_in", "tie_in_number", "tie_in_no", "tag", "tie_point", "ti"],
        "sheet_number": ["sheet_number", "sheet", "drawing_number", "drawing_no"],
        "description": ["description", "scope", "service"],
        "status": ["status", "state"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.MTO: {
        "tag": ["tag", "item_tag", "line_number", "item_no", "item"],
        "material": ["material", "description", "item_description"],
        "size": ["size", "nominal_size", "nps", "diameter"],
        "quantity": ["quantity", "qty", "count"],
        "spec": ["spec", "specification", "class"],
        "notes": ["notes", "comment", "remarks"],
    },
    FileRole.ALIAS_TABLE: {
        "alias": ["old", "alias", "from", "source", "drawing_tag"],
        "canonical": ["new", "canonical", "to", "target", "reference_tag"],
    },
    FileRole.IGNORE_PATTERNS: {
        "pattern": ["pattern", "regex", "ignore", "suppress"],
    },
}

REQUIRED_FIELDS: dict[FileRole, list[str]] = {
    FileRole.DRAWING_INDEX: ["sheet_number"],
    FileRole.DRAWING_REGISTER: ["sheet_number"],
    FileRole.VALVE_LIST: ["tag"],
    FileRole.LINE_LIST: ["tag"],
    FileRole.INSTRUMENT_INDEX: ["tag"],
    FileRole.EQUIPMENT_LIST: ["tag"],
    FileRole.SPEC_LIST: ["spec"],
    FileRole.TIE_IN_LIST: ["tag"],
    FileRole.ALIAS_TABLE: ["alias", "canonical"],
    FileRole.IGNORE_PATTERNS: ["pattern"],
}

KEY_FIELD_BY_ROLE: dict[FileRole, str] = {
    FileRole.DRAWING_INDEX: "sheet_number",
    FileRole.DRAWING_REGISTER: "sheet_number",
    FileRole.VALVE_LIST: "tag",
    FileRole.LINE_LIST: "tag",
    FileRole.INSTRUMENT_INDEX: "tag",
    FileRole.EQUIPMENT_LIST: "tag",
    FileRole.SPEC_LIST: "spec",
    FileRole.TIE_IN_LIST: "tag",
    FileRole.MTO: "tag",
    FileRole.ALIAS_TABLE: "alias",
    FileRole.IGNORE_PATTERNS: "pattern",
}

REFERENCE_TABLE_ROLES = set(ROLE_COLUMN_CANDIDATES)


def reference_mapping_path(project_root: Path) -> Path:
    return Path(project_root) / "profiles" / REFERENCE_MAPPING_FILE


def load_reference_mapping_payload(project_root: Path) -> dict[str, Any]:
    path = reference_mapping_path(project_root)
    if not path.exists():
        return {"version": 1, "roles": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "roles": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "roles": {}}
    roles = payload.get("roles")
    if not isinstance(roles, dict):
        payload["roles"] = {}
    return payload


def load_reference_mappings(project_root: Path) -> dict[FileRole, dict[str, str]]:
    payload = load_reference_mapping_payload(project_root)
    mappings: dict[FileRole, dict[str, str]] = {}
    for role_value, mapping in payload.get("roles", {}).items():
        try:
            role = FileRole(role_value)
        except ValueError:
            continue
        if isinstance(mapping, dict):
            mappings[role] = {str(field): str(column) for field, column in mapping.items() if str(column).strip()}
    return mappings


def save_reference_mapping(project_db_path: Path, role: FileRole, mapping: dict[str, str]) -> ReferenceMappingRecord:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project()
    if project is None:
        raise MissingInputError("Project not found for reference mapping save.")
    clean_mapping = {str(field): str(column).strip() for field, column in mapping.items() if str(column).strip()}
    payload = load_reference_mapping_payload(project.root_path)
    payload["version"] = 1
    payload.setdefault("roles", {})[role.value] = clean_mapping
    payload["updated_at"] = now_iso()
    path = reference_mapping_path(project.root_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ReferenceMappingRecord(project_id=project.id, role=role, mapping=clean_mapping, updated_at=payload["updated_at"], path=path)


def list_reference_mapping_records(project_db_path: Path) -> list[ReferenceMappingRecord]:
    repo = ProjectRepository(project_db_path)
    project = repo.get_project()
    if project is None:
        raise MissingInputError("Project not found for reference mappings.")
    payload = load_reference_mapping_payload(project.root_path)
    updated_at = str(payload.get("updated_at") or "")
    path = reference_mapping_path(project.root_path)
    records: list[ReferenceMappingRecord] = []
    for role, mapping in load_reference_mappings(project.root_path).items():
        records.append(ReferenceMappingRecord(project_id=project.id, role=role, mapping=mapping, updated_at=updated_at, path=path))
    return records


def apply_saved_reference_mappings(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    saved = load_reference_mappings(project_root)
    column_mapping = config.setdefault("column_mapping", {})
    for role, mapping in saved.items():
        role_key = role.value
        role_map = column_mapping.setdefault(role_key, {})
        for field, saved_column in mapping.items():
            existing = role_map.get(field, [])
            if isinstance(existing, str):
                existing = [existing]
            role_map[field] = [saved_column, *[item for item in existing if item != saved_column]]
    return config


def infer_column_mapping(headers: list[str], role: FileRole) -> dict[str, str]:
    inferred: dict[str, str] = {}
    for field, candidates in ROLE_COLUMN_CANDIDATES.get(role, {}).items():
        column = pick_column(headers, candidates)
        if column:
            inferred[field] = column
    return inferred


def _valid_saved_mapping(headers: list[str], saved_mapping: dict[str, str], role: FileRole) -> tuple[dict[str, str], list[ValidationIssue]]:
    header_set = set(headers)
    valid: dict[str, str] = {}
    issues: list[ValidationIssue] = []
    for field, column in saved_mapping.items():
        if field not in ROLE_COLUMN_CANDIDATES.get(role, {}):
            issues.append(ValidationIssue(
                level="warning",
                code="UNKNOWN_COLUMN_MAPPING_FIELD",
                message=f"Saved mapping field '{field}' is not recognized for {role.value}.",
                role=role,
                details={"field": field, "column": column},
            ))
        elif column in header_set:
            valid[field] = column
        else:
            issues.append(ValidationIssue(
                level="warning",
                code="BAD_COLUMN_MAPPING",
                message=f"Saved mapping for {role.value}.{field} points to missing column '{column}'.",
                role=role,
                details={"field": field, "column": column, "headers": headers},
            ))
    return valid, issues


def _primary_value_pattern(role: FileRole, key_field: str) -> re.Pattern[str] | None:
    if key_field == "sheet_number":
        return re.compile(r"^(?=.*\d)[A-Z]{0,5}[-_ ]?\d{2,5}[A-Z]?$", re.IGNORECASE)
    if key_field == "tag" and role == FileRole.LINE_LIST:
        return re.compile(r"^(?=.*\d)[A-Z0-9\"'/._ -]{3,}$", re.IGNORECASE)
    if key_field == "tag":
        return re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9._ -]{3,}$", re.IGNORECASE)
    if key_field == "spec":
        return re.compile(r"^[A-Z0-9._ -]{2,}$", re.IGNORECASE)
    return None


def _analyze_table_values(
    record: FileRecord,
    rows: list[dict[str, str]],
    effective_mapping: dict[str, str],
) -> tuple[list[ValidationIssue], list[ReferencePreviewRow]]:
    issues: list[ValidationIssue] = []
    preview: list[ReferencePreviewRow] = []
    key_field = KEY_FIELD_BY_ROLE.get(record.role)
    key_column = effective_mapping.get(key_field or "") if key_field else None

    blank_rows: list[int] = []
    suspicious_rows: list[dict[str, Any]] = []
    duplicate_examples: list[dict[str, Any]] = []
    key_counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    pattern = _primary_value_pattern(record.role, key_field or "")

    for idx, row in enumerate(rows, start=2):
        key_value = str(row.get(key_column, "") or "").strip() if key_column else ""
        row_warnings: list[str] = []
        if key_column and not key_value:
            blank_rows.append(idx)
            row_warnings.append("blank key")
        normalized = normalize_value(key_value, fuzzy=True, remove_separators=True) if key_value else ""
        if normalized:
            key_counts[normalized] += 1
            if normalized in first_seen and len(duplicate_examples) < 10:
                duplicate_examples.append({"value": key_value, "rows": [first_seen[normalized], idx]})
            first_seen.setdefault(normalized, idx)
        if key_value and pattern and not pattern.match(key_value):
            suspicious_rows.append({"value": key_value, "row": idx})
            row_warnings.append("suspicious key format")

        values = {field: str(row.get(column, "") or "").strip() for field, column in effective_mapping.items()}
        if len(preview) < 5:
            preview.append(ReferencePreviewRow(row_number=idx, key_value=key_value, values=values, warnings=row_warnings))

    if blank_rows and key_column:
        issues.append(ValidationIssue(
            level="warning",
            code="BLANK_REFERENCE_KEYS",
            message=f"{record.file_name} has {len(blank_rows)} blank value(s) in mapped key column '{key_column}'.",
            file_id=record.id,
            role=record.role,
            details={"field": key_field, "column": key_column, "rows": blank_rows[:20], "count": len(blank_rows)},
        ))

    if duplicate_examples:
        duplicate_count = sum(count - 1 for count in key_counts.values() if count > 1)
        issues.append(ValidationIssue(
            level="warning",
            code="DUPLICATE_REFERENCE_KEYS",
            message=f"{record.file_name} has {duplicate_count} duplicate mapped key value(s) in '{key_column}'.",
            file_id=record.id,
            role=record.role,
            details={"field": key_field, "column": key_column, "examples": duplicate_examples},
        ))

    if suspicious_rows and len(suspicious_rows) >= max(3, int(len(rows) * 0.3)):
        issues.append(ValidationIssue(
            level="warning",
            code="SUSPICIOUS_REFERENCE_VALUES",
            message=f"{record.file_name} has many values in '{key_column}' that do not look like expected {record.role.value} identifiers.",
            file_id=record.id,
            role=record.role,
            details={"field": key_field, "column": key_column, "examples": suspicious_rows[:20], "count": len(suspicious_rows)},
        ))

    for pressure_field in ["maop", "design_pressure", "test_pressure"]:
        column = effective_mapping.get(pressure_field)
        if not column:
            continue
        bad = [
            {"row": idx, "value": str(row.get(column, "") or "").strip()}
            for idx, row in enumerate(rows, start=2)
            if str(row.get(column, "") or "").strip() and not re.search(r"\d+(?:\.\d+)?", str(row.get(column, "")))
        ]
        if bad:
            issues.append(ValidationIssue(
                level="warning",
                code="SUSPICIOUS_REFERENCE_VALUES",
                message=f"{record.file_name} has non-numeric values in mapped pressure column '{column}'.",
                file_id=record.id,
                role=record.role,
                details={"field": pressure_field, "column": column, "examples": bad[:20], "count": len(bad)},
            ))

    return issues, preview


def analyze_reference_file(
    record: FileRecord,
    saved_mappings: dict[FileRole, dict[str, str]] | None = None,
    preview_limit: int = 5,
) -> ReferenceAnalysis:
    saved_mapping = (saved_mappings or {}).get(record.role, {})
    required_fields = REQUIRED_FIELDS.get(record.role, [])
    issues: list[ValidationIssue] = []

    if record.extension not in {".csv", ".xlsx", ".xlsm"}:
        if record.role in REFERENCE_TABLE_ROLES and record.extension == ".pdf":
            issues.append(ValidationIssue(
                level="warning",
                code="PDF_REFERENCE_TEXT_ONLY",
                message=f"{record.file_name} is assigned to {record.role.value}, but structured reconciliation currently uses CSV/XLSX columns. This PDF will be preserved as reference evidence.",
                file_id=record.id,
                role=record.role,
            ))
        return ReferenceAnalysis(
            file_id=record.id,
            file_name=record.file_name,
            role=record.role,
            extension=record.extension,
            required_fields=required_fields,
            saved_mapping=saved_mapping,
            issues=issues,
        )

    try:
        headers, rows = read_table(record.local_path)
    except Exception as exc:
        return ReferenceAnalysis(
            file_id=record.id,
            file_name=record.file_name,
            role=record.role,
            extension=record.extension,
            required_fields=required_fields,
            saved_mapping=saved_mapping,
            issues=[ValidationIssue(level="error", code="TABLE_UNREADABLE", message=f"{record.file_name} could not be read as a table: {exc}", file_id=record.id, role=record.role)],
        )

    if not headers:
        issues.append(ValidationIssue(level="error", code="TABLE_NO_HEADERS", message=f"{record.file_name} does not have a readable header row.", file_id=record.id, role=record.role))
        return ReferenceAnalysis(file_id=record.id, file_name=record.file_name, role=record.role, extension=record.extension, required_fields=required_fields, saved_mapping=saved_mapping, issues=issues)

    if not rows:
        issues.append(ValidationIssue(level="warning", code="TABLE_NO_ROWS", message=f"{record.file_name} has headers but no data rows.", file_id=record.id, role=record.role))

    inferred = infer_column_mapping(headers, record.role)
    valid_saved, mapping_issues = _valid_saved_mapping(headers, saved_mapping, record.role)
    for issue in mapping_issues:
        issue.file_id = record.id
    effective = dict(inferred)
    effective.update(valid_saved)

    missing = [field for field in required_fields if not effective.get(field)]
    if missing:
        issues.append(ValidationIssue(
            level="error",
            code="MISSING_REQUIRED_COLUMNS",
            message=f"{record.file_name} is missing required mapped column(s): {', '.join(missing)}.",
            file_id=record.id,
            role=record.role,
            details={"headers": headers, "missing": missing, "inferred_mapping": inferred, "saved_mapping": saved_mapping},
        ))

    issues.extend(mapping_issues)
    value_issues, preview = _analyze_table_values(record, rows, effective)
    issues.extend(value_issues)

    return ReferenceAnalysis(
        file_id=record.id,
        file_name=record.file_name,
        role=record.role,
        extension=record.extension,
        headers=headers,
        row_count=len(rows),
        required_fields=required_fields,
        inferred_mapping=inferred,
        saved_mapping=saved_mapping,
        effective_mapping=effective,
        preview_rows=preview[:preview_limit],
        issues=issues,
    )


def analyze_project_references(files: list[FileRecord], project_root: Path | None = None) -> list[ReferenceAnalysis]:
    saved = load_reference_mappings(project_root) if project_root else {}
    analyses: list[ReferenceAnalysis] = []
    for record in files:
        if record.role == FileRole.DRAWING_SET:
            continue
        if record.role == FileRole.UNKNOWN and record.extension not in {".csv", ".xlsx", ".xlsm"}:
            continue
        analyses.append(analyze_reference_file(record, saved))
    return analyses
