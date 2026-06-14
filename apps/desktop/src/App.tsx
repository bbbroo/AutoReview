import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  Alert24Regular,
  ArrowSync24Regular,
  ArrowUpload24Regular,
  CheckmarkCircle24Regular,
  ChevronRight24Regular,
  Cloud24Regular,
  Cube24Regular,
  DismissCircle24Regular,
  Document24Regular,
  DocumentBulletList24Regular,
  DocumentPdf24Regular,
  Folder24Regular,
  FolderOpen24Regular,
  HatGraduation24Regular,
  History24Regular,
  Info24Regular,
  Play24Regular,
  PlayCircle24Regular,
  Save24Regular,
  Settings24Regular,
  Sparkle24Regular,
  Warning24Regular
} from "@fluentui/react-icons";
import { api } from "./api";
import type {
  FileRecord,
  FileRole,
  FindingRecord,
  FindingStatus,
  PacketFindingScope,
  PacketMode,
  ProjectRecord,
  ReferenceAnalysis,
  RegressionResult,
  RuleMetadata,
  RunComparisonSummary,
  RunRecord,
  RunWithProgress,
  Severity,
  TrainingSetRecord,
  ValidationIssue
} from "./types";
import { FILE_ROLES, FINDING_STATUSES, SEVERITIES } from "./types";
import "./styles.css";

type Section = "setup" | "files" | "profiles" | "run" | "findings" | "export" | "history" | "training" | "settings";

const sections: Array<{ id: Section; label: string; icon: ReactNode }> = [
  { id: "setup", label: "Project Setup", icon: <Folder24Regular /> },
  { id: "files", label: "Input Files", icon: <FolderOpen24Regular /> },
  { id: "profiles", label: "Profiles & Rules", icon: <Document24Regular /> },
  { id: "run", label: "Run Status", icon: <PlayCircle24Regular /> },
  { id: "findings", label: "Findings Review", icon: <DocumentBulletList24Regular /> },
  { id: "export", label: "Packet Export", icon: <ArrowUpload24Regular /> },
  { id: "history", label: "Run History", icon: <History24Regular /> },
  { id: "training", label: "Training", icon: <HatGraduation24Regular /> },
  { id: "settings", label: "Settings", icon: <Settings24Regular /> }
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

const BOOTSTRAP_TIMEOUT_MS = 2500;

function defaultScopeForPacketMode(mode: PacketMode): PacketFindingScope {
  if (mode === "backcheck") return "backcheck";
  if (mode === "full_debug") return "all";
  return "accepted_only";
}

function displayError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return message.toLowerCase().includes("failed to fetch") ? "Failed to fetch" : message;
}

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
  const [referenceAnalyses, setReferenceAnalyses] = useState<ReferenceAnalysis[]>([]);
  const [rules, setRules] = useState<RuleMetadata[]>([]);
  const [profiles, setProfiles] = useState<Record<string, unknown>>({});
  const [profile, setProfile] = useState("balanced");
  const [newFileRole, setNewFileRole] = useState<FileRole>("unknown");
  const [currentRun, setCurrentRun] = useState<RunWithProgress | null>(null);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [findings, setFindings] = useState<FindingRecord[]>([]);
  const [selectedFindingId, setSelectedFindingId] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [packetMode, setPacketMode] = useState<PacketMode>("internal_qa");
  const [packetScope, setPacketScope] = useState<PacketFindingScope>("accepted_only");
  const [packetPath, setPacketPath] = useState("");
  const [comparison, setComparison] = useState<RunComparisonSummary | null>(null);
  const [trainingSets, setTrainingSets] = useState<TrainingSetRecord[]>([]);
  const [selectedTrainingSetId, setSelectedTrainingSetId] = useState("");
  const [regression, setRegression] = useState<RegressionResult | null>(null);
  const [missedMessage, setMissedMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const selectedFinding = findings.find((item) => item.id === selectedFindingId) ?? findings[0] ?? null;
  const currentSection = sections.find((item) => item.id === section);
  const runPercent = currentRun?.progress.at(-1)?.percent ?? (currentRun?.run.status === "completed" ? 100 : 0);

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
      const bootstrapData = Promise.all([api.health(), api.projects(), api.rules(), api.profiles()]);
      const offlineTimeout = new Promise<never>((_, reject) => {
        window.setTimeout(() => reject(new Error("Failed to fetch")), BOOTSTRAP_TIMEOUT_MS);
      });
      const [healthResult, projectList, ruleList, profileMap] = await Promise.race([bootstrapData, offlineTimeout]);
      setHealth(healthResult.mode);
      setProjects(projectList);
      setRules(ruleList);
      setProfiles(profileMap);
      setMessage((current) => (current === "Failed to fetch" ? "" : current));
    } catch (error) {
      setHealth("backend unavailable");
      setMessage(displayError(error));
    }
  }

  async function loadProjectData(nextProject: ProjectRecord) {
    setProject(nextProject);
    const [fileList, runList, trainingList, analyses] = await Promise.all([
      api.files(nextProject.id),
      api.history(nextProject.id),
      api.trainingSets(nextProject.id),
      api.referenceAnalysis(nextProject.id)
    ]);
    setFiles(fileList);
    setHistory(runList);
    setTrainingSets(trainingList);
    setReferenceAnalyses(analyses);
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
      setMessage(displayError(error));
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
      setMessage(displayError(error));
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
      setFiles(await api.files(project.id));
      setValidation(await api.validate(project.id));
      setReferenceAnalyses(await api.referenceAnalysis(project.id));
    } catch (error) {
      setMessage(displayError(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateRole(file: FileRecord, role: FileRole) {
    if (!project) return;
    await api.updateFileRole(project.id, file.id, role);
    setFiles(await api.files(project.id));
    setValidation(await api.validate(project.id));
    setReferenceAnalyses(await api.referenceAnalysis(project.id));
  }

  async function validateInputs() {
    if (!project) return;
    setValidation(await api.validate(project.id));
  }

  async function analyzeReferences() {
    if (!project) return;
    setBusy(true);
    try {
      const [issues, analyses] = await Promise.all([api.validate(project.id), api.referenceAnalysis(project.id)]);
      setValidation(issues);
      setReferenceAnalyses(analyses);
      setMessage(`Analyzed ${analyses.length} reference file(s).`);
    } catch (error) {
      setMessage(displayError(error));
    } finally {
      setBusy(false);
    }
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
      setMessage(displayError(error));
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
      const packet = await api.exportPacket(currentRun.run.id, packetScope, packetMode);
      setPacketPath(packet.packet_path);
      setMessage(`Packet exported with ${packet.finding_count} finding(s).`);
    } catch (error) {
      setMessage(displayError(error));
    } finally {
      setBusy(false);
    }
  }

  async function openPacket() {
    if (packetPath && window.autoreview) await window.autoreview.openPath(packetPath);
  }

  function updatePacketMode(mode: PacketMode) {
    setPacketMode(mode);
    setPacketScope(defaultScopeForPacketMode(mode));
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

  return (
    <FluentProvider theme={webLightTheme}>
      <div className="desktop-stage">
        <div className="app-shell">
          <aside className="sidebar">
            <div className="window-controls" aria-hidden="true">
              <span className="traffic traffic-red" />
              <span className="traffic traffic-yellow" />
              <span className="traffic traffic-green" />
            </div>
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
                  <span className="nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
            <button className="backend-card" type="button" onClick={() => void bootstrap()}>
              <span className="backend-icon"><Cloud24Regular /></span>
              <span>
                <strong>Backend Status</strong>
                <small className={health === "local-only" ? "available" : "unavailable"}>{health === "local-only" ? "Available" : "Unavailable"}</small>
              </span>
              <ChevronRight24Regular />
            </button>
          </aside>

          <main className="workspace">
            <header className="topbar">
              <div className="topbar-title">
                <div className="header-orb"><Cube24Regular /></div>
                <div>
                  <h2>{currentSection?.label}</h2>
                  <span><i />{project ? project.name : "No project open"}</span>
                </div>
              </div>
              <div className="topbar-actions">
                {busy && <Spinner size="tiny" />}
                <Button className="header-button" icon={<ArrowSync24Regular />} onClick={() => void bootstrap()}>Refresh</Button>
                <span className="header-divider" />
                <button className="icon-button" type="button" aria-label="Notifications"><Alert24Regular /></button>
                <button className="avatar-button" type="button" aria-label="Account">AR</button>
              </div>
            </header>

            {message && (
              <div className="message">
                <div className="message-body">
                  <Warning24Regular />
                  <span>{message}</span>
                </div>
                <button onClick={() => setMessage("")}>Dismiss</button>
              </div>
            )}

            {section === "setup" && (
              <SetupSection
                projectName={projectName}
                projectParent={projectParent}
                projects={projects}
                setProjectName={setProjectName}
                setProjectParent={setProjectParent}
                chooseDirectory={chooseDirectory}
                createNewProject={createNewProject}
                openExistingProject={openExistingProject}
                loadProjectData={loadProjectData}
              />
            )}

            {section === "files" && (
              <section className="panel">
                <div className="toolbar">
                  <select value={newFileRole} onChange={(event) => setNewFileRole(event.target.value as FileRole)}>
                    {FILE_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}
                  </select>
                  <Button appearance="primary" icon={<Add24Regular />} disabled={!project} onClick={() => void browseAndIngestFiles()}>Add Files</Button>
                  <Button icon={<CheckmarkCircle24Regular />} disabled={!project} onClick={() => void validateInputs()}>Validate</Button>
                  <Button icon={<DocumentBulletList24Regular />} disabled={!project} onClick={() => void analyzeReferences()}>Analyze References</Button>
                </div>
                <FileTable files={files} onRoleChange={updateRole} />
                <ValidationList issues={validation} />
                <ReferencePreview analyses={referenceAnalyses} />
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
                <div className="diagnostic-grid">
                  <div><strong>Run ID</strong><span>{currentRun?.run.id ?? "none"}</span></div>
                  <div><strong>Profile</strong><span>{currentRun?.run.profile ?? profile}</span></div>
                  <div><strong>Output Folder</strong><span>{currentRun?.run.output_dir ?? "not created"}</span></div>
                  <div><strong>Started</strong><span>{currentRun?.run.started_at ?? "not started"}</span></div>
                  <div><strong>Completed</strong><span>{currentRun?.run.completed_at ?? "not completed"}</span></div>
                  <div><strong>Warnings</strong><span>{currentRun?.run.warnings.length ?? 0}</span></div>
                </div>
                {currentRun?.run.error_message && <div className="error-callout">{currentRun.run.error_message}</div>}
                {!!currentRun?.run.warnings.length && (
                  <ul className="warning-list">
                    {currentRun.run.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                )}
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
                  <FindingFilters filters={filters} setFilters={setFilters} disciplines={disciplines} ruleIds={ruleIds} />
                  <FindingsTable findings={filteredFindings} selectedId={selectedFinding?.id ?? ""} onSelect={setSelectedFindingId} onPatch={patchFinding} />
                </div>
                <FindingDetail finding={selectedFinding} onPatch={patchFinding} />
              </section>
            )}

            {section === "export" && (
              <section className="panel">
                <div className="toolbar">
                  <label>Packet mode</label>
                  <select value={packetMode} onChange={(event) => updatePacketMode(event.target.value as PacketMode)}>
                    <option value="internal_qa">internal QA</option>
                    <option value="client_review">client review</option>
                    <option value="backcheck">backcheck</option>
                    <option value="full_debug">full debug</option>
                  </select>
                  <label>Finding scope</label>
                  <select value={packetScope} onChange={(event) => setPacketScope(event.target.value as PacketFindingScope)}>
                    <option value="accepted_only">accepted only</option>
                    <option value="accepted_and_needs_review">accepted and needs review</option>
                    <option value="all_non_rejected">all non-rejected</option>
                    <option value="backcheck">backcheck</option>
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
              <TrainingSection
                project={project}
                currentRun={currentRun}
                selectedFinding={selectedFinding}
                trainingSets={trainingSets}
                selectedTrainingSetId={selectedTrainingSetId}
                regression={regression}
                missedMessage={missedMessage}
                setSelectedTrainingSetId={setSelectedTrainingSetId}
                setMissedMessage={setMissedMessage}
                createTrainingFromRun={createTrainingFromRun}
                labelSelectedFalsePositive={labelSelectedFalsePositive}
                addMissedFromForm={addMissedFromForm}
                runTrainingRegression={runTrainingRegression}
              />
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
      </div>
    </FluentProvider>
  );
}

function SetupSection({
  projectName,
  projectParent,
  projects,
  setProjectName,
  setProjectParent,
  chooseDirectory,
  createNewProject,
  openExistingProject,
  loadProjectData
}: {
  projectName: string;
  projectParent: string;
  projects: ProjectRecord[];
  setProjectName: (value: string) => void;
  setProjectParent: (value: string) => void;
  chooseDirectory: () => Promise<void>;
  createNewProject: () => Promise<void>;
  openExistingProject: () => Promise<void>;
  loadProjectData: (project: ProjectRecord) => Promise<void>;
}) {
  return (
    <section className="setup-grid">
      <div className="setup-card project-card">
        <div className="card-title">
          <span className="title-accent" />
          <h3>Create or Open a Project</h3>
        </div>
        <div className="setup-form">
          <label>Project name</label>
          <Input value={projectName} contentAfter={<Sparkle24Regular className="input-sparkle" />} onChange={(_, data) => setProjectName(data.value)} />
          <label>Project parent folder</label>
          <div className="path-row">
            <Input placeholder="Select a folder or type a path" value={projectParent} onChange={(_, data) => setProjectParent(data.value)} />
            <Button icon={<FolderOpen24Regular />} onClick={() => void chooseDirectory()}>Browse</Button>
          </div>
          <div className="button-row">
            <Button appearance="primary" icon={<Add24Regular />} onClick={() => void createNewProject()}>Create Project</Button>
            <Button icon={<FolderOpen24Regular />} onClick={() => void openExistingProject()}>Open Project</Button>
          </div>
          <div className="info-callout">
            <span className="info-icon"><Info24Regular /></span>
            <div>
              <p>Projects contain your configuration, rules, and results in one place.</p>
              <button type="button" className="learn-link">Learn more <ChevronRight24Regular /></button>
            </div>
          </div>
        </div>
      </div>

      <div className="setup-card recent-card">
        <div className="recent-header">
          <h3>Recent Projects</h3>
          <button type="button">View all <ChevronRight24Regular /></button>
        </div>
        {projects.length > 0 ? (
          <div className="recent-list">
            {projects.map((item) => (
              <button key={item.id} onClick={() => void loadProjectData(item)}>
                <strong>{item.name}</strong>
                <span>{item.root_path}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="recent-empty">
            <div className="folder-illustration">
              <FolderOpen24Regular />
              <Sparkle24Regular className="sparkle sparkle-one" />
              <Sparkle24Regular className="sparkle sparkle-two" />
            </div>
            <h3>No recent projects</h3>
            <p>Your recently opened projects will appear here for quick access.</p>
          </div>
        )}
      </div>
    </section>
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

function mappingSummary(mapping: Record<string, string>) {
  const entries = Object.entries(mapping);
  if (!entries.length) return "no mapped columns";
  return entries.map(([field, column]) => `${field}: ${column}`).join(" | ");
}

function ReferencePreview({ analyses }: { analyses: ReferenceAnalysis[] }) {
  if (!analyses.length) return null;
  return (
    <div className="reference-preview">
      <div className="section-heading">
        <span className="title-accent" />
        <h3>Reference Preview</h3>
      </div>
      {analyses.map((analysis) => {
        const fields = Object.keys(analysis.effective_mapping);
        return (
          <div className="reference-preview-item" key={analysis.file_id}>
            <div className="reference-preview-header">
              <div>
                <strong>{analysis.file_name}</strong>
                <span>{roleLabel(analysis.role)} | {analysis.row_count} row(s) | {analysis.headers.length} column(s)</span>
              </div>
              <Badge appearance="filled">{analysis.issues.some((issue) => issue.level === "error") ? "needs mapping" : "mapped"}</Badge>
            </div>
            <dl className="mapping-list">
              <dt>Required</dt><dd>{analysis.required_fields.join(", ") || "none"}</dd>
              <dt>Effective mapping</dt><dd>{mappingSummary(analysis.effective_mapping)}</dd>
              <dt>Saved mapping</dt><dd>{mappingSummary(analysis.saved_mapping)}</dd>
            </dl>
            {!!analysis.issues.length && (
              <div className="reference-issues">
                {analysis.issues.map((issue, index) => (
                  <span key={`${analysis.file_id}-${issue.code}-${index}`} className={`reference-issue ${issue.level}`}>{issue.code}: {issue.message}</span>
                ))}
              </div>
            )}
            {!!analysis.preview_rows.length && !!fields.length && (
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Key</th>
                    {fields.slice(0, 6).map((field) => <th key={field}>{field}</th>)}
                    <th>Warnings</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.preview_rows.map((row) => (
                    <tr key={`${analysis.file_id}-${row.row_number}`}>
                      <td>{row.row_number}</td>
                      <td>{row.key_value || "blank"}</td>
                      {fields.slice(0, 6).map((field) => <td key={field}>{row.values[field] || ""}</td>)}
                      <td>{row.warnings.join(", ") || "none"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
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

function metadataText(metadata: Record<string, unknown>, key: string, fallback = "not provided") {
  const value = metadata[key];
  if (Array.isArray(value)) return value.length ? value.join(", ") : fallback;
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function coordinateText(finding: FindingRecord) {
  if (![finding.x0, finding.y0, finding.x1, finding.y1].some((value) => value !== 0)) return "not available";
  return `${finding.x0.toFixed(1)}, ${finding.y0.toFixed(1)}, ${finding.x1.toFixed(1)}, ${finding.y1.toFixed(1)}`;
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
  const ruleMetadata = finding.evidence.rule_metadata ?? {};

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

      <div className="trust-note">
        Deterministic draft finding. Review evidence and edit, accept, reject, or classify before packet export.
      </div>

      <div className="evidence">
        <h4>Rule Explanation</h4>
        <dl>
          <dt>Rule ID</dt><dd className="mono">{finding.rule_id}</dd>
          <dt>Rule name</dt><dd>{metadataText(ruleMetadata, "name", finding.subject)}</dd>
          <dt>Description</dt><dd>{metadataText(ruleMetadata, "description", "No rule description available.")}</dd>
          <dt>Discipline</dt><dd>{metadataText(ruleMetadata, "discipline", finding.discipline)}</dd>
          <dt>Default severity</dt><dd>{metadataText(ruleMetadata, "default_severity", finding.severity)}</dd>
          <dt>Default confidence</dt><dd>{metadataText(ruleMetadata, "default_confidence", `${Math.round(finding.confidence * 100)}%`)}</dd>
          <dt>Required inputs</dt><dd>{metadataText(ruleMetadata, "required_inputs", "drawing text")}</dd>
          <dt>Profiles</dt><dd>{metadataText(ruleMetadata, "profiles", "profile controlled")}</dd>
          <dt>False-positive notes</dt><dd>{metadataText(ruleMetadata, "false_positive_notes", "No false-positive notes documented for this rule.")}</dd>
        </dl>
      </div>

      <div className="evidence">
        <h4>Finding Evidence</h4>
        <dl>
          <dt>Why flagged</dt><dd>{finding.evidence.reason || finding.original_message}</dd>
          <dt>Original</dt><dd>{finding.original_message}</dd>
          <dt>Edited</dt><dd>{finding.edited_message}</dd>
          <dt>Matched text</dt><dd>{finding.found_text || "none"}</dd>
          <dt>Context</dt><dd>{finding.context || finding.evidence.context || "none"}</dd>
          <dt>Sheet/Page</dt><dd>{finding.sheet_number} / {finding.page_number}</dd>
          <dt>Output PDF page</dt><dd>{finding.output_pdf_page_number}</dd>
          <dt>Coordinates</dt><dd>{coordinateText(finding)}</dd>
          <dt>Confidence</dt><dd>{Math.round(finding.confidence * 100)}%</dd>
          <dt>Fingerprint</dt><dd className="mono">{finding.fingerprint}</dd>
          <dt>Reference source</dt><dd>{finding.evidence.source_file || "not linked"}</dd>
          <dt>Reference role</dt><dd>{finding.evidence.source_role || "not linked"}</dd>
          <dt>Reference row</dt><dd>{finding.evidence.source_row_number ?? "not linked"}</dd>
        </dl>
      </div>

      <div className="evidence">
        <h4>Decision History</h4>
        {finding.decision_history.length ? (
          <ol className="decision-history">
            {finding.decision_history.map((decision) => (
              <li key={decision.id}>
                <strong>{decision.field_name}</strong>
                <span>{decision.previous_value || "blank"}{" -> "}{decision.new_value || "blank"}</span>
                <small>{decision.created_at} by {decision.reviewer}</small>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No reviewer decisions recorded yet.</p>
        )}
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

function TrainingSection({
  project,
  currentRun,
  selectedFinding,
  trainingSets,
  selectedTrainingSetId,
  regression,
  missedMessage,
  setSelectedTrainingSetId,
  setMissedMessage,
  createTrainingFromRun,
  labelSelectedFalsePositive,
  addMissedFromForm,
  runTrainingRegression
}: {
  project: ProjectRecord | null;
  currentRun: RunWithProgress | null;
  selectedFinding: FindingRecord | null;
  trainingSets: TrainingSetRecord[];
  selectedTrainingSetId: string;
  regression: RegressionResult | null;
  missedMessage: string;
  setSelectedTrainingSetId: (value: string) => void;
  setMissedMessage: (value: string) => void;
  createTrainingFromRun: () => Promise<void>;
  labelSelectedFalsePositive: () => Promise<void>;
  addMissedFromForm: () => Promise<void>;
  runTrainingRegression: () => Promise<void>;
}) {
  return (
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
