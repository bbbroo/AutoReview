from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from ..schemas import (
    FileRecord,
    FileRole,
    FindingEvidence,
    FindingPatch,
    FindingRecord,
    FindingStatus,
    PacketExportRecord,
    PacketExportSettings,
    ProjectRecord,
    ProgressEvent,
    RunRecord,
    RunStatus,
    Severity,
)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def default_app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "AutoReview"
    return Path.home() / ".autoreview"


def app_index_path() -> Path:
    return default_app_data_dir() / "app.sqlite"


PROJECT_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    database_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    original_path TEXT NOT NULL,
    local_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    status TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    page_count INTEGER NOT NULL DEFAULT 0,
    issue_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS progress_events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    step TEXT NOT NULL,
    message TEXT NOT NULL,
    percent REAL,
    level TEXT NOT NULL DEFAULT 'info'
);
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    issue_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    original_message TEXT NOT NULL,
    edited_message TEXT NOT NULL,
    severity TEXT NOT NULL,
    discipline TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    output_pdf_page_number INTEGER NOT NULL,
    sheet_number TEXT NOT NULL,
    found_text TEXT NOT NULL,
    context TEXT NOT NULL,
    x0 REAL NOT NULL,
    y0 REAL NOT NULL,
    x1 REAL NOT NULL,
    y1 REAL NOT NULL,
    owner TEXT NOT NULL,
    reviewer_notes TEXT NOT NULL,
    rfi_candidate INTEGER NOT NULL,
    source TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_fingerprint ON findings(project_id, fingerprint);
CREATE TABLE IF NOT EXISTS packet_exports (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    packet_path TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    finding_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS training_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_run_id TEXT,
    name TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS training_labels (
    id TEXT PRIMARY KEY,
    training_set_id TEXT NOT NULL,
    finding_id TEXT,
    fingerprint TEXT NOT NULL,
    label TEXT NOT NULL,
    notes TEXT NOT NULL,
    save_as_suppression INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missed_findings (
    id TEXT PRIMARY KEY,
    training_set_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    sheet_number TEXT NOT NULL,
    expected_message TEXT NOT NULL,
    severity TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


APP_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    database_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(PROJECT_SCHEMA)


class AppIndex:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or app_index_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(APP_INDEX_SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_project(self, project: ProjectRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, root_path, database_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    root_path=excluded.root_path,
                    database_path=excluded.database_path,
                    updated_at=excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    str(project.root_path),
                    str(project.database_path),
                    project.created_at,
                    project.updated_at,
                ),
            )

    def list_projects(self) -> list[ProjectRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [_project_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _project_from_row(row) if row else None


class ProjectRepository(SQLiteStore):
    def save_project(self, project: ProjectRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, root_path, database_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    root_path=excluded.root_path,
                    database_path=excluded.database_path,
                    updated_at=excluded.updated_at
                """,
                (
                    project.id,
                    project.name,
                    str(project.root_path),
                    str(project.database_path),
                    project.created_at,
                    project.updated_at,
                ),
            )

    def get_project(self, project_id: str | None = None) -> ProjectRecord | None:
        with self.connect() as conn:
            if project_id:
                row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM projects LIMIT 1").fetchone()
        return _project_from_row(row) if row else None

    def add_file(self, record: FileRecord) -> FileRecord:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    id, project_id, role, original_path, local_path, file_name, extension,
                    size_bytes, sha256, warnings_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.project_id,
                    record.role.value,
                    str(record.original_path),
                    str(record.local_path),
                    record.file_name,
                    record.extension,
                    record.size_bytes,
                    record.sha256,
                    json.dumps(record.warnings),
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def list_files(self, project_id: str) -> list[FileRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM files WHERE project_id = ? ORDER BY created_at", (project_id,)).fetchall()
        return [_file_from_row(row) for row in rows]

    def get_file(self, file_id: str) -> FileRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return _file_from_row(row) if row else None

    def update_file_role(self, file_id: str, role: FileRole) -> FileRecord:
        updated_at = now_iso()
        with self.connect() as conn:
            conn.execute("UPDATE files SET role = ?, updated_at = ? WHERE id = ?", (role.value, updated_at, file_id))
        file_record = self.get_file(file_id)
        if file_record is None:
            raise KeyError(f"File not found: {file_id}")
        return file_record

    def create_run(self, project_id: str, profile: str, output_dir: Path) -> RunRecord:
        now = now_iso()
        record = RunRecord(
            id=new_id("run"),
            project_id=project_id,
            profile=profile,
            status=RunStatus.QUEUED,
            output_dir=output_dir,
            created_at=now,
            updated_at=now,
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, project_id, profile, status, output_dir, started_at, completed_at,
                    page_count, issue_count, warnings_json, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.project_id,
                    record.profile,
                    record.status.value,
                    str(record.output_dir),
                    record.started_at,
                    record.completed_at,
                    record.page_count,
                    record.issue_count,
                    json.dumps(record.warnings),
                    record.error_message,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _run_from_row(row) if row else None

    def list_runs(self, project_id: str) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM runs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        return [_run_from_row(row) for row in rows]

    def update_run(self, run_id: str, **fields: Any) -> RunRecord:
        if not fields:
            run = self.get_run(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            return run
        fields["updated_at"] = now_iso()
        normalized: dict[str, Any] = {}
        for key, value in fields.items():
            if isinstance(value, RunStatus):
                value = value.value
            if isinstance(value, Path):
                value = str(value)
            if key == "warnings":
                key = "warnings_json"
                value = json.dumps(value)
            normalized[key] = value
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        values = list(normalized.values()) + [run_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE runs SET {assignments} WHERE id = ?", values)
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        return run

    def add_progress(self, run_id: str, step: str, message: str, percent: float | None = None, level: str = "info") -> ProgressEvent:
        event = ProgressEvent(
            id=new_id("evt"),
            run_id=run_id,
            created_at=now_iso(),
            step=step,
            message=message,
            percent=percent,
            level=level,
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO progress_events (id, run_id, created_at, step, message, percent, level) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event.id, event.run_id, event.created_at, event.step, event.message, event.percent, event.level),
            )
        return event

    def list_progress(self, run_id: str) -> list[ProgressEvent]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM progress_events WHERE run_id = ? ORDER BY created_at, id", (run_id,)).fetchall()
        return [_progress_from_row(row) for row in rows]

    def find_issue_id_by_fingerprint(self, project_id: str, fingerprint: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT issue_id FROM findings
                WHERE project_id = ? AND fingerprint = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (project_id, fingerprint),
            ).fetchone()
        return str(row["issue_id"]) if row else None

    def next_issue_id(self, project_id: str, prefix: str = "AR") -> str:
        with self.connect() as conn:
            rows = conn.execute("SELECT issue_id FROM findings WHERE project_id = ?", (project_id,)).fetchall()
        highest = 0
        marker = f"{prefix}-"
        for row in rows:
            value = str(row["issue_id"])
            if value.startswith(marker):
                try:
                    highest = max(highest, int(value.split("-", 1)[1]))
                except ValueError:
                    pass
        return f"{prefix}-{highest + 1:04d}"

    def add_findings(self, findings: list[FindingRecord]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO findings (
                    id, project_id, run_id, issue_id, fingerprint, rule_id, subject,
                    original_message, edited_message, severity, discipline, confidence,
                    status, page_number, output_pdf_page_number, sheet_number, found_text,
                    context, x0, y0, x1, y1, owner, reviewer_notes, rfi_candidate,
                    source, evidence_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.id,
                        item.project_id,
                        item.run_id,
                        item.issue_id,
                        item.fingerprint,
                        item.rule_id,
                        item.subject,
                        item.original_message,
                        item.edited_message,
                        item.severity.value,
                        item.discipline,
                        item.confidence,
                        item.status.value,
                        item.page_number,
                        item.output_pdf_page_number,
                        item.sheet_number,
                        item.found_text,
                        item.context,
                        item.x0,
                        item.y0,
                        item.x1,
                        item.y1,
                        item.owner,
                        item.reviewer_notes,
                        1 if item.rfi_candidate else 0,
                        item.source,
                        item.evidence.model_dump_json(),
                        item.created_at,
                        item.updated_at,
                    )
                    for item in findings
                ],
            )

    def list_findings(self, run_id: str) -> list[FindingRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM findings WHERE run_id = ? ORDER BY issue_id", (run_id,)).fetchall()
        return [_finding_from_row(row) for row in rows]

    def get_finding(self, finding_id: str) -> FindingRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        return _finding_from_row(row) if row else None

    def patch_finding(self, finding_id: str, patch: FindingPatch) -> FindingRecord:
        values = patch.model_dump(exclude_unset=True)
        if not values:
            current = self.get_finding(finding_id)
            if current is None:
                raise KeyError(f"Finding not found: {finding_id}")
            return current
        values["updated_at"] = now_iso()
        normalized: dict[str, Any] = {}
        for key, value in values.items():
            if isinstance(value, (FindingStatus, Severity)):
                value = value.value
            if key == "rfi_candidate" and value is not None:
                value = 1 if value else 0
            normalized[key] = value
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        with self.connect() as conn:
            conn.execute(f"UPDATE findings SET {assignments} WHERE id = ?", list(normalized.values()) + [finding_id])
        current = self.get_finding(finding_id)
        if current is None:
            raise KeyError(f"Finding not found: {finding_id}")
        return current

    def add_packet_export(self, record: PacketExportRecord) -> PacketExportRecord:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO packet_exports (id, run_id, project_id, packet_path, settings_json, finding_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.run_id,
                    record.project_id,
                    str(record.packet_path),
                    record.settings.model_dump_json(),
                    record.finding_count,
                    record.created_at,
                ),
            )
        return record


def _project_from_row(row: sqlite3.Row) -> ProjectRecord:
    return ProjectRecord(
        id=row["id"],
        name=row["name"],
        root_path=Path(row["root_path"]),
        database_path=Path(row["database_path"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _file_from_row(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        id=row["id"],
        project_id=row["project_id"],
        role=FileRole(row["role"]),
        original_path=Path(row["original_path"]),
        local_path=Path(row["local_path"]),
        file_name=row["file_name"],
        extension=row["extension"],
        size_bytes=int(row["size_bytes"]),
        sha256=row["sha256"],
        warnings=json.loads(row["warnings_json"] or "[]"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=row["id"],
        project_id=row["project_id"],
        profile=row["profile"],
        status=RunStatus(row["status"]),
        output_dir=Path(row["output_dir"]),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        page_count=int(row["page_count"]),
        issue_count=int(row["issue_count"]),
        warnings=json.loads(row["warnings_json"] or "[]"),
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _progress_from_row(row: sqlite3.Row) -> ProgressEvent:
    return ProgressEvent(
        id=row["id"],
        run_id=row["run_id"],
        created_at=row["created_at"],
        step=row["step"],
        message=row["message"],
        percent=row["percent"],
        level=row["level"],
    )


def _finding_from_row(row: sqlite3.Row) -> FindingRecord:
    return FindingRecord(
        id=row["id"],
        project_id=row["project_id"],
        run_id=row["run_id"],
        issue_id=row["issue_id"],
        fingerprint=row["fingerprint"],
        rule_id=row["rule_id"],
        subject=row["subject"],
        original_message=row["original_message"],
        edited_message=row["edited_message"],
        severity=Severity(row["severity"]),
        discipline=row["discipline"],
        confidence=float(row["confidence"]),
        status=FindingStatus(row["status"]),
        page_number=int(row["page_number"]),
        output_pdf_page_number=int(row["output_pdf_page_number"]),
        sheet_number=row["sheet_number"],
        found_text=row["found_text"],
        context=row["context"],
        x0=float(row["x0"]),
        y0=float(row["y0"]),
        x1=float(row["x1"]),
        y1=float(row["y1"]),
        owner=row["owner"],
        reviewer_notes=row["reviewer_notes"],
        rfi_candidate=bool(row["rfi_candidate"]),
        source=row["source"],
        evidence=FindingEvidence.model_validate_json(row["evidence_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
