from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from ..errors import UnsupportedFileError, ValidationError
from ..schemas import FileRecord, FileRole, ValidationIssue
from ..storage.sqlite import ProjectRepository, new_id, now_iso


SUPPORTED_BY_ROLE: dict[FileRole, set[str]] = {
    FileRole.DRAWING_SET: {".pdf"},
    FileRole.DRAWING_INDEX: {".csv", ".xlsx", ".xlsm", ".pdf"},
    FileRole.VALVE_LIST: {".csv", ".xlsx", ".xlsm"},
    FileRole.LINE_LIST: {".csv", ".xlsx", ".xlsm"},
    FileRole.INSTRUMENT_INDEX: {".csv", ".xlsx", ".xlsm"},
    FileRole.EQUIPMENT_LIST: {".csv", ".xlsx", ".xlsm"},
    FileRole.DESIGN_BASIS: {".pdf", ".docx", ".txt"},
    FileRole.SPEC_LIST: {".csv", ".xlsx", ".xlsm", ".pdf", ".docx"},
    FileRole.TIE_IN_LIST: {".csv", ".xlsx", ".xlsm", ".pdf"},
    FileRole.MTO: {".csv", ".xlsx", ".xlsm", ".pdf"},
    FileRole.DRAWING_REGISTER: {".csv", ".xlsx", ".xlsm", ".pdf"},
    FileRole.ALIAS_TABLE: {".csv", ".txt"},
    FileRole.IGNORE_PATTERNS: {".csv", ".txt"},
    FileRole.UNKNOWN: {".pdf", ".csv", ".xlsx", ".xlsm", ".docx", ".txt"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_. -]+", "_", name).strip()
    return stem or "input_file"


def infer_file_role(path: Path) -> FileRole:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".pdf" and any(token in name for token in ["drawing", "ifc", "set", "skid", "sta", "station"]):
        return FileRole.DRAWING_SET
    if "drawing" in name and ("index" in name or "register" in name):
        return FileRole.DRAWING_INDEX if "index" in name else FileRole.DRAWING_REGISTER
    if "valve" in name:
        return FileRole.VALVE_LIST
    if "line" in name:
        return FileRole.LINE_LIST
    if "instrument" in name or "loop" in name:
        return FileRole.INSTRUMENT_INDEX
    if "equipment" in name or "asset" in name:
        return FileRole.EQUIPMENT_LIST
    if "design" in name or "basis" in name:
        return FileRole.DESIGN_BASIS
    if "spec" in name or "standard" in name:
        return FileRole.SPEC_LIST
    if "tie" in name:
        return FileRole.TIE_IN_LIST
    if "mto" in name or "material" in name or "bom" in name:
        return FileRole.MTO
    if "alias" in name:
        return FileRole.ALIAS_TABLE
    if "ignore" in name or "suppress" in name:
        return FileRole.IGNORE_PATTERNS
    if suffix == ".pdf":
        return FileRole.DRAWING_SET
    return FileRole.UNKNOWN


def validate_supported_extension(path: Path, role: FileRole) -> None:
    allowed = SUPPORTED_BY_ROLE.get(role, SUPPORTED_BY_ROLE[FileRole.UNKNOWN])
    if path.suffix.lower() not in allowed:
        raise UnsupportedFileError(
            f"{path.name} is not supported for role '{role.value}'. Supported extensions: {', '.join(sorted(allowed))}.",
            details={"path": str(path), "role": role.value, "extension": path.suffix.lower()},
        )


def project_subdir_for_role(role: FileRole) -> str:
    if role == FileRole.DRAWING_SET:
        return "inputs/drawings"
    if role in {FileRole.ALIAS_TABLE, FileRole.IGNORE_PATTERNS}:
        return "profiles"
    return "inputs/references"


def ingest_file(
    repo: ProjectRepository,
    project_id: str,
    project_root: Path,
    source_path: Path,
    role: FileRole | None = None,
    copy_into_project: bool = True,
) -> FileRecord:
    source_path = Path(source_path)
    if not source_path.exists():
        raise ValidationError(f"Selected file could not be found: {source_path}", details={"path": str(source_path)})
    if not source_path.is_file():
        raise ValidationError(f"Selected path is not a file: {source_path}", details={"path": str(source_path)})

    inferred = role or infer_file_role(source_path)
    validate_supported_extension(source_path, inferred)

    local_path = source_path
    if copy_into_project:
        target_dir = project_root / project_subdir_for_role(inferred)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / safe_file_name(source_path.name)
        if target.exists() and source_path.resolve() != target.resolve():
            target = target_dir / f"{source_path.stem}_{new_id('file')}{source_path.suffix}"
        if source_path.resolve() != target.resolve():
            shutil.copy2(source_path, target)
        local_path = target

    warnings: list[str] = []
    if local_path.stat().st_size == 0:
        warnings.append("File is empty.")

    now = now_iso()
    record = FileRecord(
        id=new_id("file"),
        project_id=project_id,
        role=inferred,
        original_path=source_path,
        local_path=local_path,
        file_name=local_path.name,
        extension=local_path.suffix.lower(),
        size_bytes=local_path.stat().st_size,
        sha256=sha256_file(local_path),
        warnings=warnings,
        created_at=now,
        updated_at=now,
    )
    return repo.add_file(record)


def validate_file_record(record: FileRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    path = record.local_path
    if not path.exists():
        issues.append(ValidationIssue(level="error", code="FILE_NOT_FOUND", message=f"{record.file_name} could not be found.", file_id=record.id, role=record.role))
        return issues
    if record.size_bytes == 0 or path.stat().st_size == 0:
        issues.append(ValidationIssue(level="error", code="BLANK_FILE", message=f"{record.file_name} is blank.", file_id=record.id, role=record.role))
    allowed = SUPPORTED_BY_ROLE.get(record.role, SUPPORTED_BY_ROLE[FileRole.UNKNOWN])
    if path.suffix.lower() not in allowed:
        issues.append(ValidationIssue(level="error", code="UNSUPPORTED_EXTENSION", message=f"{record.file_name} has unsupported extension for {record.role.value}.", file_id=record.id, role=record.role))
    if record.extension == ".docx":
        issues.append(ValidationIssue(level="warning", code="DOCX_TEXT_ONLY", message="DOCX parsing is planned; this MVP will include a text-render placeholder rather than direct Word rendering.", file_id=record.id, role=record.role))
    return issues
