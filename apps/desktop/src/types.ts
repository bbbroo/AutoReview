export type FileRole =
  | "drawing_set"
  | "drawing_index"
  | "valve_list"
  | "line_list"
  | "instrument_index"
  | "equipment_list"
  | "design_basis"
  | "spec_list"
  | "tie_in_list"
  | "mto"
  | "drawing_register"
  | "alias_table"
  | "ignore_patterns"
  | "unknown";

export type Severity = "Critical" | "Major" | "Minor" | "Info";
export type PacketMode = "internal_qa" | "client_review" | "backcheck" | "full_debug";
export type PacketFindingScope =
  | "accepted_only"
  | "accepted_and_needs_review"
  | "all_non_rejected"
  | "backcheck"
  | "all";
export type FindingStatus =
  | "Draft"
  | "Accepted"
  | "Rejected"
  | "Needs Review"
  | "Needs More Information"
  | "RFI Candidate"
  | "Backcheck Required"
  | "Closed";

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface ProjectRecord {
  id: string;
  name: string;
  root_path: string;
  database_path: string;
  created_at: string;
  updated_at: string;
}

export interface FileRecord {
  id: string;
  project_id: string;
  role: FileRole;
  original_path: string;
  local_path: string;
  file_name: string;
  extension: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  updated_at: string;
  warnings: string[];
}

export interface ValidationIssue {
  level: "info" | "warning" | "error";
  code: string;
  message: string;
  file_id?: string;
  role?: FileRole;
  details?: Record<string, unknown>;
}

export interface ReferencePreviewRow {
  row_number: number;
  key_value: string;
  values: Record<string, string>;
  warnings: string[];
}

export interface ReferenceAnalysis {
  file_id: string;
  file_name: string;
  role: FileRole;
  extension: string;
  headers: string[];
  row_count: number;
  required_fields: string[];
  inferred_mapping: Record<string, string>;
  saved_mapping: Record<string, string>;
  effective_mapping: Record<string, string>;
  preview_rows: ReferencePreviewRow[];
  issues: ValidationIssue[];
}

export interface ReferenceMappingRecord {
  project_id: string;
  role: FileRole;
  mapping: Record<string, string>;
  updated_at: string;
  path: string;
}

export interface RuleMetadata {
  rule_id: string;
  name: string;
  description: string;
  discipline: string;
  default_severity: Severity;
  default_confidence: number;
  required_inputs: FileRole[];
  profiles: string[];
  output_type: string;
  false_positive_notes: string;
  enabled_by_default: boolean;
}

export interface RunRecord {
  id: string;
  project_id: string;
  profile: string;
  status: RunStatus;
  output_dir: string;
  started_at?: string;
  completed_at?: string;
  page_count: number;
  issue_count: number;
  warnings: string[];
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface ProgressEvent {
  id: string;
  run_id: string;
  created_at: string;
  step: string;
  message: string;
  percent?: number;
  level: string;
}

export interface FindingEvidence {
  reason: string;
  context: string;
  matched_text: string;
  source_file: string;
  source_role?: FileRole;
  source_row_number?: number;
  coordinates: Record<string, number>;
  rule_metadata: Record<string, unknown>;
}

export interface FindingDecisionRecord {
  id: string;
  project_id: string;
  run_id: string;
  finding_id: string;
  issue_id: string;
  created_at: string;
  field_name: string;
  previous_value: string;
  new_value: string;
  reviewer: string;
  note: string;
}

export interface FindingRecord {
  id: string;
  project_id: string;
  run_id: string;
  issue_id: string;
  fingerprint: string;
  rule_id: string;
  subject: string;
  original_message: string;
  edited_message: string;
  severity: Severity;
  discipline: string;
  confidence: number;
  status: FindingStatus;
  page_number: number;
  output_pdf_page_number: number;
  sheet_number: string;
  found_text: string;
  context: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  owner: string;
  reviewer_notes: string;
  rfi_candidate: boolean;
  source: string;
  evidence: FindingEvidence;
  decision_history: FindingDecisionRecord[];
  created_at: string;
  updated_at: string;
}

export interface RunWithProgress {
  run: RunRecord;
  progress: ProgressEvent[];
}

export interface PacketExportRecord {
  id: string;
  run_id: string;
  project_id: string;
  packet_path: string;
  settings: Record<string, unknown>;
  finding_count: number;
  created_at: string;
}

export interface RunComparisonSummary {
  base_run_id: string;
  compare_run_id: string;
  new_issue_ids: string[];
  resolved_issue_ids: string[];
  repeated_issue_ids: string[];
  carryover_issue_ids: string[];
  status_changed_issue_ids: string[];
  severity_changed_issue_ids: string[];
  message_changed_issue_ids: string[];
  changed: Array<Record<string, unknown>>;
}

export interface TrainingSetRecord {
  id: string;
  project_id: string;
  source_run_id?: string;
  name: string;
  notes: string;
  golden_path?: string;
  created_at: string;
}

export interface TrainingLabelRecord {
  id: string;
  training_set_id: string;
  finding_id?: string;
  fingerprint: string;
  label: string;
  notes: string;
  save_as_suppression: boolean;
  created_at: string;
}

export interface RegressionResult {
  training_set_id: string;
  source_run_id?: string;
  expected_count: number;
  actual_count: number;
  missing_fingerprints: string[];
  new_fingerprints: string[];
  changed: Array<Record<string, unknown>>;
  false_positive_count: number;
  missed_finding_count: number;
  rule_performance: Array<{
    rule_id: string;
    expected_count: number;
    actual_count: number;
    matched_count: number;
    missing_count: number;
    new_count: number;
    changed_count: number;
    correct_count: number;
    false_positive_count: number;
    needs_better_wording_count: number;
    rule_needs_tuning_count: number;
    missed_finding_count: number;
  }>;
}

export const FILE_ROLES: FileRole[] = [
  "drawing_set",
  "drawing_index",
  "valve_list",
  "line_list",
  "instrument_index",
  "equipment_list",
  "design_basis",
  "spec_list",
  "tie_in_list",
  "mto",
  "drawing_register",
  "alias_table",
  "ignore_patterns",
  "unknown"
];

export const FINDING_STATUSES: FindingStatus[] = [
  "Draft",
  "Accepted",
  "Rejected",
  "Needs Review",
  "Needs More Information",
  "RFI Candidate",
  "Backcheck Required",
  "Closed"
];

export const SEVERITIES: Severity[] = ["Critical", "Major", "Minor", "Info"];
