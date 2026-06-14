import { useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  FluentProvider,
  Input,
  ProgressBar,
  Spinner,
  Textarea,
  webLightTheme
} from "@fluentui/react-components";
import {
  Add24Regular,
  ArrowClockwise24Regular,
  CheckmarkCircle24Regular,
  DismissCircle24Regular,
  DocumentPdf24Regular,
  FolderOpen24Regular,
  Play24Regular,
  Save24Regular
} from "@fluentui/react-icons";
import { api } from "./api";
import type {
  FileRecord,
  FileRole,
  FindingRecord,
  FindingStatus,
  ProjectRecord,
  RuleMetadata,
  RunComparisonSummary,
  RunRecord,
  RunWithProgress,
  Severity,
  RegressionResult,
  TrainingSetRecord,
  ValidationIssue
} from "./types";
import { FILE_ROLES, FINDING_STATUSES, SEVERITIES } from "./types";
import "./styles.css";

type Section = "setup" | "files" | "profiles" | "run" | "findings" | "export" | "history" | "training" | "settings";

const sections: Array<{ id: Section; label: string }> = [
  { id: "setup", label: "Project Setup" },
  { id: "files", label: "Input Files" },
  { id: "profiles", label: "Profiles & Rules" },
  { id: "run", label: "Run Status" },
  { id: "findings", label: "Findings Review" },
  { id: "export", label: "Packet Export" },
  { id: "history", label: "Run History" },
  { id: "training", label: "Training" },
  { id: "settings", label: "Settings" }
];

const emptyFilters = {
  severity: "",
  status: "",
  discipline: "",
  rule: "",
  sheet: "",
  rfi: "",
  text: ""
};

function roleLabel(value: string) {
  return value.replaceAll("_", " ");
}

function severityClass(severity: Severity) {
  return `severity severity-${severity.toLowerCase()}`;
}

function statusClass(status: FindingStatus) {
  return `status status-${status.toLowerCase().replaceAll(" ", "-")}`;
}

export default function App() {
  const [section, setSection] = useState<Section>("setup");
  const [health, setHealth] = useState("starting");
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [projectName, setProjectName] = useState("New AutoReview Project");
  const [projectParent, setProjectParent] = useState("");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [validation, setValidation] = useState<ValidationIssue[]>([]);
  const [rules, setRules] = useState<RuleMetadata[]>([]);
  const [profiles, setProfiles] = useState<Record<string, unknown>>({});
  const [profile, setProfile] = useState("balanced");
  const [newFileRole, setNewFileRole] = useState<FileRole>("unknown");
  const [currentRun, setCurrentRun] = useState<RunWithProgress | null>(null);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [findings, setFindings] = useState<FindingRecord[]>([]);
  const [selectedFindingId, setSelectedFindingId] = useState<string>("");
  const [filters, setFilters] = useState(emptyFilters);
  const [packetScope, setPacketScope] = useState("accepted_only");
  const [packetPath, setPacketPath] = useState("");
  const [comparison, setComparison] = useState<RunComparisonSummary | null>(null);
  const [trainingSets, setTrainingSets] = useState<TrainingSetRecord[]>([]);
  const [selectedTrainingSetId, setSelectedTrainingSetId] = useState("");
  const [regression, setRegression] = useState<RegressionResult | null>(null);
  const [missedMessage, setMissedMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const selectedFinding = findings.find((item) => item.id === selectedFindingId) ?? findings[0] ?? null;

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!currentRun || !["queued", "running"].includes(currentRun.run.status)) return;
    const timer = window.setInterval(async () => {
      const updated = await api.run(currentRun.run.id);
      setCurrentRun(updated);
      if (updated.run.status === "completed" || updated.run.status === "failed") {
        await loadRunDetails(updated.run.id);
        if (project) await loadProjectData(project);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [currentRun?.run.id, currentRun?.run.status, project?.id]);

  async function bootstrap() {
    try {
      const [healthResult, projectList, ruleList, profileMap] = await Promise.all([
        api.health(),
        api.projects(),
        api.rules(),
        api.profiles()
      ]);
      setHealth(healthResult.mode);
      setProjects(projectList);
      setRules(ruleList);
      setProfiles(profileMap);
    } catch (error) {
      setHealth("backend unavailable");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function loadProjectData(nextProject: ProjectRecord) {
    setProject(nextProject);
    const [fileList, runList, trainingList] = await Promise.all([
      api.files(nextProject.id),
      api.history(nextProject.id),
      api.trainingSets(nextProject.id)
    ]);
    setFiles(fileList);
    setHistory(runList);
    setTrainingSets(trainingList);
    setSelectedTrainingSetId((current) => current || trainingList[0]?.id || "");
    if (runList[0]) {
      const run = await api.run(runList[0].id);
      setCurrentRun(run);
      await loadRunDetails(run.run.id);
    } else {
      setCurrentRun(null);
      setFindings([]);
    }
  }

  async function loadRunDetails(runId: string) {
    const [run, findingList] = await Promise.all([api.run(runId), api.findings(runId)]);
    setCurrentRun(run);
    setFindings(findingList);
    setSelectedFindingId((current) => current || findingList[0]?.id || "");
  }

  async function chooseDirectory() {
    const selected = window.autoreview ? await window.autoreview.selectDirectory() : window.prompt("Project parent folder path");
    if (selected) setProjectParent(selected);
  }

  async function createNewProject() {
    if (!projectName.trim() || !projectParent.trim()) return;
    setBusy(true);
    try {
      const created = await api.createProject(projectName.trim(), projectParent.trim());
      await bootstrap();
      await loadProjectData(created);
      setSection("files");
      setMessage(`Project created: ${created.root_path}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function openExistingProject() {
    const selected = window.autoreview ? await window.autoreview.selectDirectory() : window.prompt("Project folder path");
    if (!selected) return;
    setBusy(true);
    try {
      const opened = await api.openProject(selected);
      await bootstrap();
      await loadProjectData(opened);
      setSection("files");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function browseAndIngestFiles() {
    if (!project) return;
    const paths = window.autoreview ? await window.autoreview.selectFiles() : (window.prompt("File paths separated by semicolons") ?? "").split(";").filter(Boolean);
    if (!paths.length) return;
    setBusy(true);
    try {
      await api.ingestFiles(project.id, paths, newFileRole === "unknown" ? undefined : newFileRole);
      const fileList = await api.files(project.id);
      setFiles(fileList);
      setValidation(await api.validate(project.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateRole(file: FileRecord, role: FileRole) {
    if (!project) return;
    await api.updateFileRole(project.id, file.id, role);
    setFiles(await api.files(project.id));
    setValidation(await api.validate(project.id));
  }

  async function validateInputs() {
    if (!project) return;
    setValidation(await api.validate(project.id));
  }

  async function startRun() {
    if (!project) return;
    setBusy(true);
    try {
      const issues = await api.validate(project.id);
      setValidation(issues);
      if (issues.some((item) => item.level === "error")) {
        setSection("files");
        setMessage("Resolve validation errors before running.");
        return;
      }
      const run = await api.startRun(project.id, profile);
      setCurrentRun({ run, progress: [] });
      setFindings([]);
      setPacketPath("");
      setSection("run");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function patchFinding(finding: FindingRecord, patch: Parameters<typeof api.patchFinding>[1]) {
    const updated = await api.patchFinding(finding.id, patch);
    setFindings((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    setSelectedFindingId(updated.id);
  }

  async function exportPacket() {
    if (!currentRun) return;
    setBusy(true);
    try {
      const packet = await api.exportPacket(currentRun.run.id, packetScope);
      setPacketPath(packet.packet_path);
      setMessage(`Packet exported with ${packet.finding_count} finding(s).`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function openPacket() {
    if (packetPath && window.autoreview) await window.autoreview.openPath(packetPath);
  }

  async function compareLatestRuns() {
    if (history.length < 2) return;
    setComparison(await api.compareRuns(history[1].id, history[0].id));
  }

  async function createTrainingFromRun() {
    if (!project || !currentRun) return;
    const created = await api.createTrainingSet(project.id, `${project.name} ${currentRun.run.id}`, currentRun.run.id, "Created from desktop review run.");
    const list = await api.trainingSets(project.id);
    setTrainingSets(list);
    setSelectedTrainingSetId(created.id);
    setRegression(null);
  }

  async function labelSelectedFalsePositive() {
    if (!selectedTrainingSetId || !selectedFinding) return;
    await api.labelFinding(selectedTrainingSetId, selectedFinding.id, "false_positive", "Marked from desktop review.", true);
    setMessage(`${selectedFinding.issue_id} labeled as false positive.`);
  }

  async function addMissedFromForm() {
    if (!selectedTrainingSetId || !missedMessage.trim()) return;
    await api.addMissedFinding(selectedTrainingSetId, selectedFinding?.rule_id ?? "MANUAL_EXPECTED_FINDING", selectedFinding?.sheet_number ?? "Drawing Set", missedMessage.trim());
    setMissedMessage("");
    setMessage("Missed finding added to training set.");
  }

  async function runTrainingRegression() {
    if (!selectedTrainingSetId) return;
    setRegression(await api.runRegression(selectedTrainingSetId, currentRun?.run.id));
  }

  const filteredFindings = useMemo(() => {
    return findings.filter((finding) => {
      if (filters.severity && finding.severity !== filters.severity) return false;
      if (filters.status && finding.status !== filters.status) return false;
      if (filters.discipline && finding.discipline !== filters.discipline) return false;
      if (filters.rule && finding.rule_id !== filters.rule) return false;
      if (filters.sheet && !finding.sheet_number.toLowerCase().includes(filters.sheet.toLowerCase())) return false;
      if (filters.rfi && String(finding.rfi_candidate) !== filters.rfi) return false;
      if (filters.text) {
        const blob = `${finding.issue_id} ${finding.subject} ${finding.edited_message} ${finding.found_text}`.toLowerCase();
        if (!blob.includes(filters.text.toLowerCase())) return false;
      }
      return true;
    });
  }, [findings, filters]);

  const disciplines = Array.from(new Set(findings.map((item) => item.discipline).filter(Boolean))).sort();
  const ruleIds = Array.from(new Set(findings.map((item) => item.rule_id).filter(Boolean))).sort();
  const runPercent = currentRun?.progress.at(-1)?.percent ?? (currentRun?.run.status === "completed" ? 100 : 0);

  return (
    <FluentProvider theme={webLightTheme}>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">AR</div>
            <div>
              <h1>AutoReview</h1>
              <span>{health}</span>
            </div>
          </div>
          <nav>
            {sections.map((item) => (
              <button key={item.id} className={section === item.id ? "active" : ""} onClick={() => setSection(item.id)}>
                {item.label}
              </button>
            ))}
          </nav>
        </aside>

        <main className="workspace">
          <header className="topbar">
            <div>
              <h2>{sections.find((item) => item.id === section)?.label}</h2>
              <span>{project ? project.name : "No project open"}</span>
            </div>
            <div className="topbar-actions">
              {busy && <Spinner size="tiny" />}
              <Button icon={<ArrowClockwise24Regular />} onClick={() => void bootstrap()}>Refresh</Button>
            </div>
          </header>

          {message && (
            <div className="message">
              <span>{message}</span>
              <button onClick={() => setMessage("")}>Dismiss</button>
            </div>
          )}

          {section === "setup" && (
            <section className="panel setup-grid">
              <div className="setup-form">
                <label>Project name</label>
                <Input value={projectName} onChange={(_, data) => setProjectName(data.value)} />
                <label>Project parent folder</label>
                <div className="path-row">
                  <Input value={projectParent} onChange={(_, data) => setProjectParent(data.value)} />
                  <Button icon={<FolderOpen24Regular />} onClick={() => void chooseDirectory()}>Browse</Button>
                </div>
                <div className="button-row">
                  <Button appearance="primary" icon={<Add24Regular />} onClick={() => void createNewProject()}>Create Project</Button>
                  <Button icon={<FolderOpen24Regular />} onClick={() => void openExistingProject()}>Open Project</Button>
                </div>
              </div>
              <div className="recent-list">
                <h3>Recent Projects</h3>
                {projects.map((item) => (
                  <button key={item.id} onClick={() => void loadProjectData(item)}>
                    <strong>{item.name}</strong>
                    <span>{item.root_path}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {section === "files" && (
            <section className="panel">
              <div className="toolbar">
                <select value={newFileRole} onChange={(event) => setNewFileRole(event.target.value as FileRole)}>
                  {FILE_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}
                </select>
                <Button appearance="primary" icon={<Add24Regular />} disabled={!project} onClick={() => void browseAndIngestFiles()}>Add Files</Button>
                <Button icon={<CheckmarkCircle24Regular />} disabled={!project} onClick={() => void validateInputs()}>Validate</Button>
              </div>
              <FileTable files={files} onRoleChange={updateRole} />
              <ValidationList issues={validation} />
            </section>
          )}

          {section === "profiles" && (
            <section className="panel">
              <div className="toolbar">
                <label>Review profile</label>
                <select value={profile} onChange={(event) => setProfile(event.target.value)}>
                  {Object.keys(profiles).map((name) => <option key={name} value={name}>{name.replaceAll("_", " ")}</option>)}
                </select>
              </div>
              <RulesTable rules={rules} />
            </section>
          )}

          {section === "run" && (
            <section className="panel">
              <div className="run-summary">
                <Button appearance="primary" icon={<Play24Regular />} disabled={!project || busy || currentRun?.run.status === "running"} onClick={() => void startRun()}>
                  Run Review
                </Button>
                <div>
                  <strong>{currentRun?.run.status ?? "not started"}</strong>
                  <span>{currentRun?.run.issue_count ?? 0} finding(s), {currentRun?.run.page_count ?? 0} page(s)</span>
                </div>
              </div>
              <ProgressBar value={runPercent / 100} />
              <ol className="progress-list">
                {currentRun?.progress.map((event) => (
                  <li key={event.id} className={event.level === "error" ? "error" : ""}>
                    <span>{event.step}</span>
                    <p>{event.message}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {section === "findings" && (
            <section className="findings-layout">
              <div className="panel findings-table-panel">
                <FindingFilters
                  filters={filters}
                  setFilters={setFilters}
                  disciplines={disciplines}
                  ruleIds={ruleIds}
                />
                <FindingsTable
                  findings={filteredFindings}
                  selectedId={selectedFinding?.id ?? ""}
                  onSelect={setSelectedFindingId}
                  onPatch={patchFinding}
                />
              </div>
              <FindingDetail finding={selectedFinding} onPatch={patchFinding} />
            </section>
          )}

          {section === "export" && (
            <section className="panel">
              <div className="toolbar">
                <label>Finding scope</label>
                <select value={packetScope} onChange={(event) => setPacketScope(event.target.value)}>
                  <option value="accepted_only">accepted only</option>
                  <option value="accepted_and_needs_review">accepted and needs review</option>
                  <option value="all_non_rejected">all non-rejected</option>
                  <option value="all">all findings</option>
                </select>
                <Button appearance="primary" icon={<DocumentPdf24Regular />} disabled={!currentRun} onClick={() => void exportPacket()}>Export Packet</Button>
                <Button disabled={!packetPath || !window.autoreview} onClick={() => void openPacket()}>Open Packet</Button>
              </div>
              {packetPath && <div className="output-path">{packetPath}</div>}
            </section>
          )}

          {section === "history" && (
            <section className="panel">
              <div className="toolbar">
                <Button disabled={history.length < 2} onClick={() => void compareLatestRuns()}>Compare Latest Runs</Button>
              </div>
              <RunHistory runs={history} onOpen={(run) => void loadRunDetails(run.id)} />
              {comparison && <ComparisonSummary comparison={comparison} />}
            </section>
          )}

          {section === "training" && (
            <section className="panel training-panel">
              <div className="toolbar">
                <Button disabled={!project || !currentRun} onClick={() => void createTrainingFromRun()}>Create Training Set</Button>
                <select value={selectedTrainingSetId} onChange={(event) => setSelectedTrainingSetId(event.target.value)}>
                  <option value="">training set</option>
                  {trainingSets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <Button disabled={!selectedTrainingSetId || !selectedFinding} onClick={() => void labelSelectedFalsePositive()}>Mark False Positive</Button>
                <Button disabled={!selectedTrainingSetId} onClick={() => void runTrainingRegression()}>Run Regression</Button>
              </div>
              <div className="training-grid">
                <div>
                  <h3>Training Sets</h3>
                  <table className="data-table">
                    <thead><tr><th>Name</th><th>Source Run</th><th>Golden</th></tr></thead>
                    <tbody>
                      {trainingSets.map((item) => (
                        <tr key={item.id} onClick={() => setSelectedTrainingSetId(item.id)}>
                          <td><strong>{item.name}</strong><span>{item.id}</span></td>
                          <td className="mono">{item.source_run_id ?? ""}</td>
                          <td>{item.golden_path ? "yes" : "no"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3>Missed Finding</h3>
                  <Textarea value={missedMessage} resize="vertical" onChange={(_, data) => setMissedMessage(data.value)} />
                  <Button disabled={!selectedTrainingSetId || !missedMessage.trim()} onClick={() => void addMissedFromForm()}>Add Missed Finding</Button>
                  {regression && (
                    <div className="regression-result">
                      <div><strong>{regression.expected_count}</strong><span>expected</span></div>
                      <div><strong>{regression.actual_count}</strong><span>actual</span></div>
                      <div><strong>{regression.missing_fingerprints.length}</strong><span>missing</span></div>
                      <div><strong>{regression.new_fingerprints.length}</strong><span>new</span></div>
                      <div><strong>{regression.changed.length}</strong><span>changed</span></div>
                      <div><strong>{regression.false_positive_count}</strong><span>false positive</span></div>
                      <div><strong>{regression.missed_finding_count}</strong><span>missed</span></div>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

          {section === "settings" && (
            <section className="panel settings-grid">
              <div>
                <h3>Local Processing</h3>
                <p>Backend: {health}</p>
                <p>Project database: {project?.database_path ?? "none"}</p>
              </div>
              <div>
                <h3>Current Review Profile</h3>
                <p>{profile}</p>
                <p>{rules.filter((rule) => rule.enabled_by_default).length} default deterministic rules listed.</p>
              </div>
            </section>
          )}
        </main>
      </div>
    </FluentProvider>
  );
}

function FileTable({ files, onRoleChange }: { files: FileRecord[]; onRoleChange: (file: FileRecord, role: FileRole) => void }) {
  return (
    <table className="data-table">
      <thead>
        <tr><th>Role</th><th>File</th><th>Size</th><th>Hash</th></tr>
      </thead>
      <tbody>
        {files.map((file) => (
          <tr key={file.id}>
            <td>
              <select value={file.role} onChange={(event) => void onRoleChange(file, event.target.value as FileRole)}>
                {FILE_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}
              </select>
            </td>
            <td><strong>{file.file_name}</strong><span>{file.local_path}</span></td>
            <td>{Math.round(file.size_bytes / 1024).toLocaleString()} KB</td>
            <td className="mono">{file.sha256.slice(0, 12)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ValidationList({ issues }: { issues: ValidationIssue[] }) {
  if (!issues.length) return <div className="empty-state">No validation messages.</div>;
  return (
    <div className="validation-list">
      {issues.map((issue, index) => (
        <div key={`${issue.code}-${index}`} className={`validation ${issue.level}`}>
          <Badge appearance="filled">{issue.level}</Badge>
          <span>{issue.message}</span>
        </div>
      ))}
    </div>
  );
}

function RulesTable({ rules }: { rules: RuleMetadata[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr><th>Rule</th><th>Discipline</th><th>Severity</th><th>Confidence</th><th>Inputs</th><th>Default</th></tr>
      </thead>
      <tbody>
        {rules.map((rule) => (
          <tr key={rule.rule_id}>
            <td><strong>{rule.name}</strong><span>{rule.rule_id}</span></td>
            <td>{rule.discipline}</td>
            <td><span className={severityClass(rule.default_severity)}>{rule.default_severity}</span></td>
            <td>{Math.round(rule.default_confidence * 100)}%</td>
            <td>{rule.required_inputs.map(roleLabel).join(", ") || "drawing text"}</td>
            <td>{rule.enabled_by_default ? "on" : "off"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FindingFilters({
  filters,
  setFilters,
  disciplines,
  ruleIds
}: {
  filters: typeof emptyFilters;
  setFilters: (filters: typeof emptyFilters) => void;
  disciplines: string[];
  ruleIds: string[];
}) {
  return (
    <div className="filters">
      <select value={filters.severity} onChange={(event) => setFilters({ ...filters, severity: event.target.value })}>
        <option value="">severity</option>
        {SEVERITIES.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
        <option value="">status</option>
        {FINDING_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <select value={filters.discipline} onChange={(event) => setFilters({ ...filters, discipline: event.target.value })}>
        <option value="">discipline</option>
        {disciplines.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <select value={filters.rule} onChange={(event) => setFilters({ ...filters, rule: event.target.value })}>
        <option value="">rule</option>
        {ruleIds.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <Input placeholder="sheet" value={filters.sheet} onChange={(_, data) => setFilters({ ...filters, sheet: data.value })} />
      <Input placeholder="search" value={filters.text} onChange={(_, data) => setFilters({ ...filters, text: data.value })} />
      <Button onClick={() => setFilters(emptyFilters)}>Clear</Button>
    </div>
  );
}

function FindingsTable({
  findings,
  selectedId,
  onSelect,
  onPatch
}: {
  findings: FindingRecord[];
  selectedId: string;
  onSelect: (id: string) => void;
  onPatch: (finding: FindingRecord, patch: Parameters<typeof api.patchFinding>[1]) => Promise<void>;
}) {
  return (
    <table className="data-table findings-table">
      <thead>
        <tr><th>ID</th><th>Status</th><th>Severity</th><th>Sheet</th><th>Rule</th><th>Finding</th><th>Confidence</th></tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id} className={finding.id === selectedId ? "selected" : ""} onClick={() => onSelect(finding.id)}>
            <td className="mono">{finding.issue_id}</td>
            <td><span className={statusClass(finding.status)}>{finding.status}</span></td>
            <td><span className={severityClass(finding.severity)}>{finding.severity}</span></td>
            <td>{finding.sheet_number}</td>
            <td>{finding.rule_id}</td>
            <td>
              <strong>{finding.subject}</strong>
              <span>{finding.edited_message}</span>
              <div className="quick-actions">
                <button onClick={(event) => { event.stopPropagation(); void onPatch(finding, { status: "Accepted" }); }}>accept</button>
                <button onClick={(event) => { event.stopPropagation(); void onPatch(finding, { status: "Rejected" }); }}>reject</button>
              </div>
            </td>
            <td>{Math.round(finding.confidence * 100)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FindingDetail({
  finding,
  onPatch
}: {
  finding: FindingRecord | null;
  onPatch: (finding: FindingRecord, patch: Parameters<typeof api.patchFinding>[1]) => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    setMessage(finding?.edited_message ?? "");
    setNotes(finding?.reviewer_notes ?? "");
  }, [finding?.id]);

  if (!finding) return <aside className="panel detail-panel empty-state">No finding selected.</aside>;

  return (
    <aside className="panel detail-panel">
      <div className="detail-header">
        <div>
          <h3>{finding.issue_id}</h3>
          <span>{finding.rule_id}</span>
        </div>
        <div className="button-row compact">
          <Button icon={<CheckmarkCircle24Regular />} onClick={() => void onPatch(finding, { status: "Accepted" })}>Accept</Button>
          <Button icon={<DismissCircle24Regular />} onClick={() => void onPatch(finding, { status: "Rejected" })}>Reject</Button>
        </div>
      </div>

      <label>Status</label>
      <select value={finding.status} onChange={(event) => void onPatch(finding, { status: event.target.value as FindingStatus })}>
        {FINDING_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
      </select>

      <label>Severity</label>
      <select value={finding.severity} onChange={(event) => void onPatch(finding, { severity: event.target.value as Severity })}>
        {SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
      </select>

      <label>Discipline</label>
      <Input value={finding.discipline} onChange={(_, data) => void onPatch(finding, { discipline: data.value })} />

      <label>Edited packet comment</label>
      <Textarea value={message} resize="vertical" onChange={(_, data) => setMessage(data.value)} />
      <label>Reviewer notes</label>
      <Textarea value={notes} resize="vertical" onChange={(_, data) => setNotes(data.value)} />
      <Button appearance="primary" icon={<Save24Regular />} onClick={() => void onPatch(finding, { edited_message: message, reviewer_notes: notes })}>Save Finding</Button>

      <div className="evidence">
        <h4>Evidence</h4>
        <dl>
          <dt>Original</dt><dd>{finding.original_message}</dd>
          <dt>Matched text</dt><dd>{finding.found_text || "none"}</dd>
          <dt>Context</dt><dd>{finding.context || finding.evidence.context || "none"}</dd>
          <dt>Sheet/Page</dt><dd>{finding.sheet_number} / {finding.page_number}</dd>
          <dt>Coordinates</dt><dd>{finding.x0}, {finding.y0}, {finding.x1}, {finding.y1}</dd>
          <dt>Fingerprint</dt><dd className="mono">{finding.fingerprint}</dd>
        </dl>
      </div>
    </aside>
  );
}

function RunHistory({ runs, onOpen }: { runs: RunRecord[]; onOpen: (run: RunRecord) => void }) {
  return (
    <table className="data-table">
      <thead><tr><th>Run</th><th>Status</th><th>Profile</th><th>Findings</th><th>Pages</th><th>Completed</th></tr></thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id} onClick={() => onOpen(run)}>
            <td className="mono">{run.id}</td>
            <td>{run.status}</td>
            <td>{run.profile}</td>
            <td>{run.issue_count}</td>
            <td>{run.page_count}</td>
            <td>{run.completed_at ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ComparisonSummary({ comparison }: { comparison: RunComparisonSummary }) {
  return (
    <div className="comparison">
      <div><strong>{comparison.new_issue_ids.length}</strong><span>new</span></div>
      <div><strong>{comparison.resolved_issue_ids.length}</strong><span>resolved</span></div>
      <div><strong>{comparison.repeated_issue_ids.length}</strong><span>repeated</span></div>
      <div><strong>{comparison.changed.length}</strong><span>changed</span></div>
    </div>
  );
}
