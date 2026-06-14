from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    INFO = "Info"


class FindingStatus(str, Enum):
    DRAFT = "Draft"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    NEEDS_REVIEW = "Needs Review"
    NEEDS_MORE_INFORMATION = "Needs More Information"
    RFI_CANDIDATE = "RFI Candidate"
    BACKCHECK_REQUIRED = "Backcheck Required"
    CLOSED = "Closed"


class FileRole(str, Enum):
    DRAWING_SET = "drawing_set"
    DRAWING_INDEX = "drawing_index"
    VALVE_LIST = "valve_list"
    LINE_LIST = "line_list"
    INSTRUMENT_INDEX = "instrument_index"
    EQUIPMENT_LIST = "equipment_list"
    DESIGN_BASIS = "design_basis"
    SPEC_LIST = "spec_list"
    TIE_IN_LIST = "tie_in_list"
    MTO = "mto"
    DRAWING_REGISTER = "drawing_register"
    ALIAS_TABLE = "alias_table"
    IGNORE_PATTERNS = "ignore_patterns"
    UNKNOWN = "unknown"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PacketFindingScope(str, Enum):
    ACCEPTED_ONLY = "accepted_only"
    ACCEPTED_AND_NEEDS_REVIEW = "accepted_and_needs_review"
    ALL_NON_REJECTED = "all_non_rejected"
    BACKCHECK = "backcheck"
    ALL = "all"


class PacketMode(str, Enum):
    INTERNAL_QA = "internal_qa"
    CLIENT_REVIEW = "client_review"
    BACKCHECK = "backcheck"
    FULL_DEBUG = "full_debug"


class ReviewProfileName(str, Enum):
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    REGULATOR_STATION = "regulator_station"
    P_AND_ID = "p_and_id"
    PIPELINE_CROSSING = "pipeline_crossing"
    CUSTOM = "custom"


class ValidationIssue(BaseModel):
    level: str = Field(pattern="^(info|warning|error)$")
    code: str
    message: str
    file_id: str | None = None
    role: FileRole | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(BaseModel):
    name: str
    root_path: Path


class ProjectRecord(BaseModel):
    id: str
    name: str
    root_path: Path
    database_path: Path
    created_at: str
    updated_at: str


class FileIngestRequest(BaseModel):
    paths: list[Path]
    role: FileRole | None = None
    copy_into_project: bool = True


class FileRecord(BaseModel):
    id: str
    project_id: str
    role: FileRole
    original_path: Path
    local_path: Path
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    created_at: str
    updated_at: str
    warnings: list[str] = Field(default_factory=list)


class ReferencePreviewRow(BaseModel):
    row_number: int
    key_value: str = ""
    values: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ReferenceAnalysis(BaseModel):
    file_id: str
    file_name: str
    role: FileRole
    extension: str
    headers: list[str] = Field(default_factory=list)
    row_count: int = 0
    required_fields: list[str] = Field(default_factory=list)
    inferred_mapping: dict[str, str] = Field(default_factory=dict)
    saved_mapping: dict[str, str] = Field(default_factory=dict)
    effective_mapping: dict[str, str] = Field(default_factory=dict)
    preview_rows: list[ReferencePreviewRow] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)


class ReferenceMappingPatch(BaseModel):
    mapping: dict[str, str] = Field(default_factory=dict)


class ReferenceMappingRecord(BaseModel):
    project_id: str
    role: FileRole
    mapping: dict[str, str] = Field(default_factory=dict)
    updated_at: str
    path: Path


class RuleMetadata(BaseModel):
    rule_id: str
    name: str
    description: str
    discipline: str
    default_severity: Severity
    default_confidence: float = Field(ge=0.0, le=1.0)
    required_inputs: list[FileRole] = Field(default_factory=list)
    profiles: list[str] = Field(default_factory=list)
    output_type: str = "finding"
    false_positive_notes: str = ""
    enabled_by_default: bool = True


class ReviewProfile(BaseModel):
    id: str
    name: str
    description: str
    rules_enabled: dict[str, bool] = Field(default_factory=dict)
    severity_overrides: dict[str, Severity] = Field(default_factory=dict)
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    settings: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    profile: str = ReviewProfileName.BALANCED.value
    config_path: Path | None = None


class RunRecord(BaseModel):
    id: str
    project_id: str
    profile: str
    status: RunStatus
    output_dir: Path
    started_at: str | None = None
    completed_at: str | None = None
    page_count: int = 0
    issue_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    error_message: str = ""
    created_at: str
    updated_at: str


class ProgressEvent(BaseModel):
    id: str
    run_id: str
    created_at: str
    step: str
    message: str
    percent: float | None = None
    level: str = "info"


class FindingEvidence(BaseModel):
    reason: str
    context: str = ""
    matched_text: str = ""
    source_file: str = ""
    source_role: FileRole | None = None
    source_row_number: int | None = None
    coordinates: dict[str, float] = Field(default_factory=dict)
    rule_metadata: dict[str, Any] = Field(default_factory=dict)


class FindingDecisionRecord(BaseModel):
    id: str
    project_id: str
    run_id: str
    finding_id: str
    issue_id: str
    created_at: str
    field_name: str
    previous_value: str
    new_value: str
    reviewer: str = "local_user"
    note: str = ""


class FindingRecord(BaseModel):
    id: str
    project_id: str
    run_id: str
    issue_id: str
    fingerprint: str
    rule_id: str
    subject: str
    original_message: str
    edited_message: str
    severity: Severity
    discipline: str
    confidence: float
    status: FindingStatus
    page_number: int
    output_pdf_page_number: int
    sheet_number: str
    found_text: str
    context: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    owner: str = ""
    reviewer_notes: str = ""
    rfi_candidate: bool = False
    source: str = "auto"
    evidence: FindingEvidence
    decision_history: list[FindingDecisionRecord] = Field(default_factory=list)
    created_at: str
    updated_at: str


class FindingPatch(BaseModel):
    status: FindingStatus | None = None
    severity: Severity | None = None
    discipline: str | None = None
    edited_message: str | None = None
    owner: str | None = None
    reviewer_notes: str | None = None
    rfi_candidate: bool | None = None


class PacketExportSettings(BaseModel):
    packet_mode: PacketMode = PacketMode.INTERNAL_QA
    finding_scope: PacketFindingScope = PacketFindingScope.ACCEPTED_ONLY
    include_reference_inputs: bool = True
    include_issue_index: bool = True
    include_critical_major_list: bool = True
    include_rejected_findings: bool = False
    include_debug_pages: bool = False
    packet_name: str = "single_review_packet.pdf"

    @model_validator(mode="after")
    def apply_packet_mode_defaults(self) -> "PacketExportSettings":
        provided = getattr(self, "model_fields_set", set())
        if "packet_mode" not in provided:
            return self

        if "finding_scope" not in provided:
            if self.packet_mode == PacketMode.BACKCHECK:
                self.finding_scope = PacketFindingScope.BACKCHECK
            elif self.packet_mode == PacketMode.FULL_DEBUG:
                self.finding_scope = PacketFindingScope.ALL
            else:
                self.finding_scope = PacketFindingScope.ACCEPTED_ONLY

        if self.packet_mode == PacketMode.FULL_DEBUG:
            self.include_rejected_findings = True
            self.include_debug_pages = True
        return self


class PacketExportRecord(BaseModel):
    id: str
    run_id: str
    project_id: str
    packet_path: Path
    settings: PacketExportSettings
    finding_count: int
    created_at: str


class RunComparison(BaseModel):
    base_run_id: str
    compare_run_id: str
    new_findings: list[FindingRecord]
    resolved_findings: list[FindingRecord]
    repeated_findings: list[FindingRecord]
    changed_findings: list[dict[str, Any]]


class TrainingLabel(str, Enum):
    CORRECT = "correct"
    FALSE_POSITIVE = "false_positive"
    MISSED_ISSUE = "missed_issue"
    NEEDS_BETTER_WORDING = "needs_better_wording"
    RULE_NEEDS_TUNING = "rule_needs_tuning"


class TrainingSetCreate(BaseModel):
    name: str
    source_project_id: str
    source_run_id: str | None = None
    notes: str = ""


class TrainingSetRecord(BaseModel):
    id: str
    project_id: str
    source_run_id: str | None = None
    name: str
    notes: str = ""
    golden_path: Path | None = None
    created_at: str


class TrainingLabelRequest(BaseModel):
    finding_id: str
    label: TrainingLabel
    notes: str = ""
    save_as_suppression: bool = False


class TrainingLabelRecord(BaseModel):
    id: str
    training_set_id: str
    finding_id: str | None = None
    fingerprint: str
    label: TrainingLabel
    notes: str = ""
    save_as_suppression: bool = False
    created_at: str


class MissedFindingCreate(BaseModel):
    rule_id: str
    sheet_number: str
    expected_message: str
    severity: Severity = Severity.MAJOR
    notes: str = ""


class MissedFindingRecord(BaseModel):
    id: str
    training_set_id: str
    rule_id: str
    sheet_number: str
    expected_message: str
    severity: Severity
    notes: str = ""
    created_at: str


class RegressionResult(BaseModel):
    training_set_id: str
    source_run_id: str | None
    expected_count: int
    actual_count: int
    missing_fingerprints: list[str] = Field(default_factory=list)
    new_fingerprints: list[str] = Field(default_factory=list)
    changed: list[dict[str, Any]] = Field(default_factory=list)
    false_positive_count: int = 0
    missed_finding_count: int = 0
