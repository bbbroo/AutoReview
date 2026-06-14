from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Optional
import time


@dataclass
class RectData:
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0

    @classmethod
    def from_rect(cls, rect: Any | None) -> "RectData":
        if rect is None:
            return cls()
        return cls(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


@dataclass
class Hit:
    text: str
    normalized: str
    kind: str
    page_index: int
    page_number: int
    sheet_number: str
    rect: RectData
    context: str = ""
    confidence: float = 0.75


@dataclass
class Issue:
    issue_id: str
    rule_id: str
    subject: str
    message: str
    severity: str = "Info"
    discipline: str = "General"
    confidence: float = 0.75
    status: str = "Draft - Engineer Review Required"
    page_number: int = 1
    output_pdf_page_number: int = 1
    sheet_number: str = ""
    found_text: str = ""
    context: str = ""
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    owner: str = ""
    response: str = ""
    backcheck_result: str = ""
    due_date: str = ""
    source: str = "auto"
    ai_suggested_comment: str = ""
    rfi_candidate: str = "No"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PageInfo:
    page_index: int
    page_number: int
    sheet_number: str
    sheet_title: str = ""
    revision: str = ""
    issue_date: str = ""
    status: str = ""
    width: float = 0.0
    height: float = 0.0
    orientation: str = ""
    rotation: int = 0
    word_count: int = 0
    image_count: int = 0
    text_quality_score: float = 0.0
    raster_only: bool = False
    garbled_text_warning: bool = False
    title_block_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class RunManifest:
    input: str
    output_dir: str
    started_at: str
    run_id: str = ""
    project_id: str = ""
    profile: str = ""
    app_version: str = ""
    engine_version: str = ""
    status: str = "running"
    completed_at: str = ""
    elapsed_seconds: float = 0.0
    page_count: int = 0
    issue_count: int = 0
    active_rule_count: int = 0
    total_rule_count: int = 0
    rule_counts: dict[str, int] = field(default_factory=dict)
    severity_counts: dict[str, int] = field(default_factory=dict)
    finding_status_counts: dict[str, int] = field(default_factory=dict)
    finding_fingerprints: list[str] = field(default_factory=list)
    finding_trace: list[dict[str, Any]] = field(default_factory=list)
    input_files: list[dict[str, Any]] = field(default_factory=list)
    output_files: list[dict[str, Any]] = field(default_factory=list)
    output_packet_path: str = ""
    marked_up_pdf_path: str = ""
    packet_export_settings: dict[str, Any] = field(default_factory=dict)
    packet_finding_count: int = 0
    settings_used: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    error_message: str = ""

    def complete(self, started_monotonic: float, page_count: int, issue_count: int) -> None:
        self.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
        self.page_count = page_count
        self.issue_count = issue_count
        self.status = "completed"
