import type {
  FileRecord,
  FileRole,
  FindingDecisionRecord,
  FindingRecord,
  FindingStatus,
  PacketFindingScope,
  PacketMode,
  PacketExportRecord,
  ProjectRecord,
  ProgressEvent,
  RuleMetadata,
  RunComparisonSummary,
  RunRecord,
  RunWithProgress,
  Severity,
  RegressionResult,
  TrainingLabelRecord,
  TrainingSetRecord,
  ValidationIssue
} from "./types";

const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body?.detail?.message ?? body?.detail ?? message;
    } catch {
      // Keep HTTP status text.
    }
    throw new Error(String(message));
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string }>("/health"),
  rules: () => request<RuleMetadata[]>("/rules"),
  profiles: () => request<Record<string, unknown>>("/profiles"),
  projects: () => request<ProjectRecord[]>("/projects"),
  createProject: (name: string, rootPath: string) =>
    request<ProjectRecord>("/projects", { method: "POST", body: JSON.stringify({ name, root_path: rootPath }) }),
  openProject: (rootPath: string) =>
    request<ProjectRecord>("/projects/open", { method: "POST", body: JSON.stringify({ root_path: rootPath }) }),
  files: (projectId: string) => request<FileRecord[]>(`/projects/${projectId}/files`),
  ingestFiles: (projectId: string, paths: string[], role?: FileRole) =>
    request<FileRecord[]>(`/projects/${projectId}/files/ingest`, {
      method: "POST",
      body: JSON.stringify({ paths, role: role ?? null, copy_into_project: true })
    }),
  updateFileRole: (projectId: string, fileId: string, role: FileRole) =>
    request<FileRecord>(`/projects/${projectId}/files/${fileId}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  validate: (projectId: string) => request<ValidationIssue[]>(`/projects/${projectId}/validate`, { method: "POST" }),
  startRun: (projectId: string, profile: string) =>
    request<RunRecord>(`/projects/${projectId}/runs`, { method: "POST", body: JSON.stringify({ profile }) }),
  run: (runId: string) => request<RunWithProgress>(`/runs/${runId}`),
  findings: (runId: string) => request<FindingRecord[]>(`/runs/${runId}/findings`),
  findingHistory: (findingId: string) => request<FindingDecisionRecord[]>(`/findings/${findingId}/history`),
  patchFinding: (
    findingId: string,
    patch: Partial<{
      status: FindingStatus;
      severity: Severity;
      discipline: string;
      edited_message: string;
      reviewer_notes: string;
      rfi_candidate: boolean;
    }>
  ) => request<FindingRecord>(`/findings/${findingId}`, { method: "PATCH", body: JSON.stringify(patch) }),
  exportPacket: (runId: string, findingScope: PacketFindingScope, packetMode: PacketMode) =>
    request<PacketExportRecord>(`/runs/${runId}/export-packet`, {
      method: "POST",
      body: JSON.stringify({
        packet_mode: packetMode,
        finding_scope: findingScope,
        include_reference_inputs: true,
        packet_name: "single_review_packet.pdf"
      })
    }),
  history: (projectId: string) => request<RunRecord[]>(`/projects/${projectId}/history`),
  compareRuns: (baseRunId: string, compareRunId: string) =>
    request<RunComparisonSummary>(`/runs/${baseRunId}/compare/${compareRunId}`),
  trainingSets: (projectId: string) => request<TrainingSetRecord[]>(`/projects/${projectId}/training-sets`),
  createTrainingSet: (projectId: string, name: string, sourceRunId: string, notes = "") =>
    request<TrainingSetRecord>(`/projects/${projectId}/training-sets`, {
      method: "POST",
      body: JSON.stringify({ name, source_project_id: projectId, source_run_id: sourceRunId, notes })
    }),
  labelFinding: (trainingSetId: string, findingId: string, label: string, notes = "", saveAsSuppression = false) =>
    request<TrainingLabelRecord>(`/training-sets/${trainingSetId}/labels`, {
      method: "POST",
      body: JSON.stringify({ finding_id: findingId, label, notes, save_as_suppression: saveAsSuppression })
    }),
  addMissedFinding: (trainingSetId: string, ruleId: string, sheetNumber: string, expectedMessage: string) =>
    request(`/training-sets/${trainingSetId}/missed-findings`, {
      method: "POST",
      body: JSON.stringify({ rule_id: ruleId, sheet_number: sheetNumber, expected_message: expectedMessage, severity: "Major" })
    }),
  runRegression: (trainingSetId: string, runId?: string) =>
    request<RegressionResult>(`/training-sets/${trainingSetId}/regression`, {
      method: "POST",
      body: JSON.stringify({ run_id: runId ?? null })
    })
};

export type { ProgressEvent };
