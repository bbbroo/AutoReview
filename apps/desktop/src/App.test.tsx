import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { FindingRecord } from "./types";

let responses: Record<string, unknown>;
let requests: Array<{ path: string; method: string; body?: unknown }>;

function baseResponses(): Record<string, unknown> {
  return {
  "/health": { status: "ok", mode: "local-only" },
  "/projects": [],
  "/rules": [
    {
      rule_id: "DRAWING_INDEX_RECONCILIATION",
      name: "Drawing Index Reconciliation",
      description: "Compares sheets against index.",
      discipline: "CAD / Document Control",
      default_severity: "Major",
      default_confidence: 0.9,
      required_inputs: ["drawing_index"],
      profiles: ["balanced"],
      output_type: "finding",
      false_positive_notes: "",
      enabled_by_default: true
    }
  ],
  "/profiles": { balanced: { rules_on: [], rules_off: [] } }
  };
}

function projectRecord() {
  return {
    id: "proj_1",
    name: "Pipeline Review",
    root_path: "C:/AutoReview/Pipeline Review",
    database_path: "C:/AutoReview/Pipeline Review/project.sqlite",
    created_at: "2026-06-14T12:00:00",
    updated_at: "2026-06-14T12:00:00"
  };
}

function runRecord(id = "run_1", completed = "2026-06-14T12:01:00") {
  return {
    id,
    project_id: "proj_1",
    profile: "balanced",
    status: "completed",
    output_dir: `C:/AutoReview/Pipeline Review/outputs/runs/${id}`,
    started_at: "2026-06-14T12:00:00",
    completed_at: completed,
    page_count: 2,
    issue_count: 2,
    warnings: [],
    error_message: "",
    created_at: "2026-06-14T12:00:00",
    updated_at: completed
  };
}

function findingRecord(overrides: Partial<FindingRecord> = {}): FindingRecord {
  return {
    id: "finding_1",
    project_id: "proj_1",
    run_id: "run_1",
    issue_id: "AR-0001",
    fingerprint: "fp-accepted",
    rule_id: "DRAWING_INDEX_RECONCILIATION",
    subject: "Drawing index mismatch",
    original_message: "Sheet P-201 missing from index.",
    edited_message: "Sheet P-201 should be added to the drawing index.",
    severity: "Major",
    discipline: "CAD / Document Control",
    confidence: 0.9,
    status: "Draft",
    page_number: 2,
    output_pdf_page_number: 5,
    sheet_number: "P-201",
    found_text: "P-201",
    context: "Callout references P-201.",
    x0: 1,
    y0: 2,
    x1: 3,
    y1: 4,
    owner: "",
    reviewer_notes: "",
    rfi_candidate: false,
    source: "auto",
    evidence: {
      reason: "Sheet P-201 was referenced but not found in the drawing index.",
      context: "Callout references P-201.",
      matched_text: "P-201",
      coordinate_source: "pdf_text_search",
      placement_type: "resolved_text_search",
      placement_confidence: 0.86,
      original_found_text: "P-201",
      resolved_match_text: "P-201",
      resolved_page_number: 2,
      placement_warning: "",
      source_file: "drawing_index.csv",
      source_role: "drawing_index",
      source_row_number: 12,
      coordinates: { x0: 1, y0: 2, x1: 3, y1: 4 },
      rule_metadata: {
        rule_id: "DRAWING_INDEX_RECONCILIATION",
        name: "Drawing Index Reconciliation",
        description: "Compares drawing sheets against the drawing index.",
        discipline: "CAD / Document Control",
        default_severity: "Major",
        default_confidence: 0.9,
        required_inputs: ["drawing_index"],
        profiles: ["balanced"],
        false_positive_notes: "Alias sheets and client title-block variants can cause noise."
      }
    },
    decision_history: [],
    created_at: "2026-06-14T12:01:00",
    updated_at: "2026-06-14T12:01:00",
    ...overrides
  } as FindingRecord;
}

describe("AutoReview desktop shell", () => {
  beforeEach(() => {
    responses = baseResponses();
    requests = [];
    Object.defineProperty(window, "autoreview", {
      configurable: true,
      value: {
        selectDirectory: vi.fn(async () => "C:/AutoReview"),
        selectFiles: vi.fn(async () => [
          "C:/inputs/sample_natural_gas_drawing_set.pdf",
          "C:/inputs/valve_list.csv"
        ]),
        openPath: vi.fn(async () => undefined)
      }
    });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const requestBody = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ path: url.pathname, method, body: requestBody });
      const handler = responses[`${method} ${url.pathname}`] ?? responses[url.pathname];
      const body = typeof handler === "function" ? (handler as (body?: unknown) => unknown)(requestBody) : (handler ?? {});
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }));
  });

  it("renders project setup and navigation", async () => {
    render(<App />);
    expect(await screen.findByText("AutoReview")).toBeInTheDocument();
    expect(screen.getAllByText("Project Setup").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Findings Review")).toBeInTheDocument();
    expect(screen.queryByLabelText("Notifications")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Account")).not.toBeInTheDocument();
    expect(screen.queryByText("Learn more")).not.toBeInTheDocument();
    expect(screen.queryByText("View all")).not.toBeInTheDocument();
    expect(screen.getByTitle("Reload local project, rule, and profile data from the sidecar.")).toBeInTheDocument();
    expect(screen.getByTitle("Name for the local project folder and SQLite review database.")).toBeInTheDocument();
  });

  it("shows rule explanation, traceability, and decision history for a selected finding", async () => {
    responses["/projects"] = [{
      id: "proj_1",
      name: "Sample Project",
      root_path: "C:/AutoReview/Sample",
      database_path: "C:/AutoReview/Sample/project.sqlite",
      created_at: "2026-06-14T12:00:00",
      updated_at: "2026-06-14T12:00:00"
    }];
    responses["/projects/proj_1/files"] = [];
    responses["/projects/proj_1/references/analysis"] = [];
    const runRecord = {
      id: "run_1",
      project_id: "proj_1",
      profile: "balanced",
      status: "completed",
      output_dir: "C:/AutoReview/Sample/outputs/runs/run_1",
      started_at: "2026-06-14T12:00:00",
      completed_at: "2026-06-14T12:01:00",
      page_count: 1,
      issue_count: 1,
      warnings: [],
      error_message: "",
      created_at: "2026-06-14T12:00:00",
      updated_at: "2026-06-14T12:01:00"
    };
    responses["/projects/proj_1/history"] = [runRecord];
    responses["/projects/proj_1/training-sets"] = [];
    responses["/runs/run_1"] = { run: runRecord, progress: [] };
    responses["/runs/run_1/findings"] = [{
      id: "finding_1",
      project_id: "proj_1",
      run_id: "run_1",
      issue_id: "AR-0001",
      fingerprint: "fingerprint123",
      rule_id: "DRAWING_INDEX_RECONCILIATION",
      subject: "Drawing index mismatch",
      original_message: "Sheet P-201 missing from index.",
      edited_message: "Reviewer edited finding.",
      severity: "Major",
      discipline: "CAD / Document Control",
      confidence: 0.9,
      status: "Accepted",
      page_number: 2,
      output_pdf_page_number: 5,
      sheet_number: "P-201",
      found_text: "P-201",
      context: "Callout references P-201.",
      x0: 1,
      y0: 2,
      x1: 3,
      y1: 4,
      owner: "",
      reviewer_notes: "Reviewer note",
      rfi_candidate: false,
      source: "auto",
      evidence: {
        reason: "Sheet P-201 was referenced but not found in the drawing index.",
        context: "Callout references P-201.",
        matched_text: "P-201",
        coordinate_source: "rule_hit",
        placement_type: "exact_hit",
        placement_confidence: 1,
        original_found_text: "P-201",
        resolved_match_text: "P-201",
        resolved_page_number: 2,
        placement_warning: "",
        source_file: "drawing_index.csv",
        source_role: "drawing_index",
        source_row_number: 12,
        coordinates: { x0: 1, y0: 2, x1: 3, y1: 4 },
        rule_metadata: {
          rule_id: "DRAWING_INDEX_RECONCILIATION",
          name: "Drawing Index Reconciliation",
          description: "Compares sheets against index.",
          discipline: "CAD / Document Control",
          default_severity: "Major",
          default_confidence: 0.9,
          required_inputs: ["drawing_index"],
          profiles: ["balanced"],
          false_positive_notes: "Sheet aliases can cause noise."
        }
      },
      decision_history: [{
        id: "decision_1",
        project_id: "proj_1",
        run_id: "run_1",
        finding_id: "finding_1",
        issue_id: "AR-0001",
        created_at: "2026-06-14T12:02:00",
        field_name: "status",
        previous_value: "Draft",
        new_value: "Accepted",
        reviewer: "local_user",
        note: "Updated through local finding review."
      }],
      created_at: "2026-06-14T12:01:00",
      updated_at: "2026-06-14T12:02:00"
    }];

    render(<App />);
    fireEvent.click(await screen.findByText("Sample Project"));
    fireEvent.click(await screen.findByText("Findings Review"));

    expect(await screen.findByText("Rule Explanation")).toBeInTheDocument();
    expect(screen.getByText("Finding Evidence")).toBeInTheDocument();
    expect(screen.getByText("Decision History")).toBeInTheDocument();
    expect(screen.getByText("Placement type")).toBeInTheDocument();
    expect(screen.getByText("exact_hit")).toBeInTheDocument();
    expect(screen.getByText("Drawing Index Reconciliation")).toBeInTheDocument();
    expect(screen.getByText("fingerprint123")).toBeInTheDocument();
    expect(screen.getByText("Draft -> Accepted")).toBeInTheDocument();
  });

  it("shows reference preview analysis for project input files", async () => {
    responses["/projects"] = [{
      id: "proj_1",
      name: "Sample Project",
      root_path: "C:/AutoReview/Sample",
      database_path: "C:/AutoReview/Sample/project.sqlite",
      created_at: "2026-06-14T12:00:00",
      updated_at: "2026-06-14T12:00:00"
    }];
    responses["/projects/proj_1/files"] = [{
      id: "file_1",
      project_id: "proj_1",
      role: "valve_list",
      original_path: "C:/inputs/custom_valves.csv",
      local_path: "C:/AutoReview/Sample/inputs/references/custom_valves.csv",
      file_name: "custom_valves.csv",
      extension: ".csv",
      size_bytes: 100,
      sha256: "abc123456789abc123",
      created_at: "2026-06-14T12:00:00",
      updated_at: "2026-06-14T12:00:00",
      warnings: []
    }];
    responses["/projects/proj_1/history"] = [];
    responses["/projects/proj_1/training-sets"] = [];
    responses["/projects/proj_1/references/analysis"] = [{
      file_id: "file_1",
      file_name: "custom_valves.csv",
      role: "valve_list",
      extension: ".csv",
      headers: ["Valve ID", "Size", "Service"],
      row_count: 2,
      required_fields: ["tag"],
      inferred_mapping: {},
      saved_mapping: { tag: "Valve ID" },
      effective_mapping: { tag: "Valve ID", size: "Size", service: "Service" },
      preview_rows: [{ row_number: 2, key_value: "BV-101", values: { tag: "BV-101", size: "2", service: "Gas" }, warnings: [] }],
      issues: []
    }];

    render(<App />);
    fireEvent.click(await screen.findByText("Sample Project"));
    fireEvent.click(await screen.findByText("Input Files"));

    expect(await screen.findByText("Reference Preview")).toBeInTheDocument();
    expect(screen.getAllByText("custom_valves.csv").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/tag: Valve ID/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("BV-101").length).toBeGreaterThanOrEqual(1);
  });

  it("covers the project-to-packet workflow through the local API surface", async () => {
    const project = projectRecord();
    const runOne = runRecord("run_1");
    const runTwo = runRecord("run_0", "2026-06-13T12:01:00");
    const files = [
      {
        id: "file_pdf",
        project_id: project.id,
        role: "drawing_set",
        original_path: "C:/inputs/sample_natural_gas_drawing_set.pdf",
        local_path: "C:/AutoReview/Pipeline Review/inputs/drawings/sample_natural_gas_drawing_set.pdf",
        file_name: "sample_natural_gas_drawing_set.pdf",
        extension: ".pdf",
        size_bytes: 2048,
        sha256: "pdfhash123456",
        created_at: "2026-06-14T12:00:00",
        updated_at: "2026-06-14T12:00:00",
        warnings: []
      },
      {
        id: "file_valves",
        project_id: project.id,
        role: "unknown",
        original_path: "C:/inputs/valve_list.csv",
        local_path: "C:/AutoReview/Pipeline Review/inputs/references/valve_list.csv",
        file_name: "valve_list.csv",
        extension: ".csv",
        size_bytes: 100,
        sha256: "valvehash123456",
        created_at: "2026-06-14T12:00:00",
        updated_at: "2026-06-14T12:00:00",
        warnings: []
      }
    ];
    const analysis = [{
      file_id: "file_valves",
      file_name: "valve_list.csv",
      role: "valve_list",
      extension: ".csv",
      headers: ["Valve ID", "Size", "Service", "Sheet"],
      row_count: 2,
      required_fields: ["tag"],
      inferred_mapping: { size: "Size", service: "Service" },
      saved_mapping: {},
      effective_mapping: { tag: "Valve ID", size: "Size", service: "Service", sheet_number: "Sheet" },
      preview_rows: [{ row_number: 2, key_value: "BV-101", values: { tag: "BV-101", size: "2", service: "Gas", sheet_number: "P-201" }, warnings: [] }],
      issues: []
    }];
    let findings = [
      findingRecord(),
      findingRecord({
        id: "finding_2",
        issue_id: "AR-0002",
        fingerprint: "fp-rejected",
        subject: "Possible duplicate sheet",
        edited_message: "Possible duplicate sheet number.",
        found_text: "P-202",
        sheet_number: "P-202",
        status: "Draft"
      })
    ];

    responses["POST /projects"] = () => {
      responses["/projects"] = [project];
      return project;
    };
    responses[`/projects/${project.id}/files`] = [];
    responses[`/projects/${project.id}/history`] = [runOne, runTwo];
    responses[`/projects/${project.id}/training-sets`] = [];
    responses[`/projects/${project.id}/references/analysis`] = [];
    responses[`POST /projects/${project.id}/files/ingest`] = () => {
      responses[`/projects/${project.id}/files`] = files;
      responses[`/projects/${project.id}/references/analysis`] = analysis;
      return files;
    };
    responses[`PATCH /projects/${project.id}/files/file_valves`] = (body?: unknown) => {
      files[1] = { ...files[1], role: (body as { role: string }).role };
      return files[1];
    };
    responses[`POST /projects/${project.id}/validate`] = [];
    responses[`PUT /projects/${project.id}/reference-mappings/valve_list`] = (body?: unknown) => ({
      project_id: project.id,
      role: "valve_list",
      mapping: (body as { mapping: Record<string, string> }).mapping,
      updated_at: "2026-06-14T12:02:00",
      path: "C:/AutoReview/Pipeline Review/profiles/reference_mappings.json"
    });
    responses[`POST /projects/${project.id}/runs`] = { ...runOne, status: "running", completed_at: null, issue_count: 0 };
    responses[`/runs/${runOne.id}`] = { run: runOne, progress: [{ id: "evt_1", run_id: runOne.id, created_at: "2026-06-14T12:01:00", step: "completed", message: "Review completed with 2 draft finding(s).", percent: 100, level: "info" }] };
    responses[`/runs/${runTwo.id}`] = { run: runTwo, progress: [] };
    responses[`/runs/${runOne.id}/findings`] = () => findings;
    responses["PATCH /findings/finding_1"] = (body?: unknown) => {
      findings = findings.map((item) => item.id === "finding_1" ? {
        ...item,
        ...(body as Record<string, unknown>),
        decision_history: [
          { id: "decision_status", project_id: project.id, run_id: runOne.id, finding_id: "finding_1", issue_id: "AR-0001", created_at: "2026-06-14T12:02:00", field_name: "status", previous_value: "Draft", new_value: "Accepted", reviewer: "local_user", note: "Updated through local finding review." }
        ]
      } : item);
      return findings[0];
    };
    responses["PATCH /findings/finding_2"] = (body?: unknown) => {
      findings = findings.map((item) => item.id === "finding_2" ? { ...item, ...(body as Record<string, unknown>) } : item);
      return findings[1];
    };
    responses[`POST /runs/${runOne.id}/export-packet`] = {
      id: "packet_1",
      run_id: runOne.id,
      project_id: project.id,
      packet_path: "C:/AutoReview/Pipeline Review/packets/single_review_packet.pdf",
      settings: { packet_mode: "client_review", finding_scope: "accepted_only" },
      finding_count: 1,
      created_at: "2026-06-14T12:03:00"
    };
    responses[`/runs/${runTwo.id}/compare/${runOne.id}`] = {
      base_run_id: runTwo.id,
      compare_run_id: runOne.id,
      new_issue_ids: ["AR-0002"],
      resolved_issue_ids: [],
      repeated_issue_ids: ["AR-0001"],
      carryover_issue_ids: ["AR-0001"],
      status_changed_issue_ids: ["AR-0001"],
      severity_changed_issue_ids: ["AR-0001"],
      message_changed_issue_ids: ["AR-0001"],
      backcheck_required_issue_ids: ["AR-0001"],
      changed: [{ issue_id: "AR-0001", fingerprint: "fp-accepted", changes: { status: { before: "Draft", after: "Accepted" } } }]
    };

    render(<App />);
    expect(await screen.findByText("AutoReview")).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("New AutoReview Project"), { target: { value: "Pipeline Review" } });
    fireEvent.click(screen.getByText("Browse"));
    await waitFor(() => expect(screen.getByDisplayValue("C:/AutoReview")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Create Project"));
    expect(await screen.findByText("No validation messages.")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Add Files"));
    await waitFor(() => expect(requests.some((request) => request.path.endsWith("/files/ingest"))).toBe(true));
    expect(window.autoreview?.selectFiles).toHaveBeenCalled();
    expect(await screen.findByText("sample_natural_gas_drawing_set.pdf")).toBeInTheDocument();

    const roleSelects = screen.getAllByRole("combobox");
    const unknownRoleSelects = roleSelects.filter((select) => (select as HTMLSelectElement).value === "unknown");
    fireEvent.change(unknownRoleSelects.at(-1)!, { target: { value: "valve_list" } });
    await waitFor(() => expect(requests.some((request) => request.method === "PATCH" && request.path.endsWith("/files/file_valves"))).toBe(true));

    fireEvent.click(screen.getByText("Validate"));
    await waitFor(() => expect(requests.some((request) => request.path.endsWith("/validate"))).toBe(true));
    expect(await screen.findByText("Reference Preview")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Map tag / line number for valve_list.csv"), { target: { value: "Valve ID" } });
    fireEvent.click(screen.getByText("Save Mapping"));
    await waitFor(() => expect(requests.some((request) => request.method === "PUT" && request.path.endsWith("/reference-mappings/valve_list"))).toBe(true));

    fireEvent.click(screen.getByText("Run Status"));
    fireEvent.click(screen.getByText("Run Review"));
    await waitFor(() => expect(requests.some((request) => request.method === "POST" && request.path.endsWith("/runs"))).toBe(true));
    fireEvent.click(await screen.findByText("Open Output Folder"));
    fireEvent.click(screen.getByText("Run Manifest"));
    fireEvent.click(screen.getByText("Trace CSV"));
    expect(window.autoreview?.openPath).toHaveBeenCalledWith("C:/AutoReview/Pipeline Review/outputs/runs/run_1");
    expect(window.autoreview?.openPath).toHaveBeenCalledWith("C:/AutoReview/Pipeline Review/outputs/runs/run_1/run_manifest.json");
    expect(window.autoreview?.openPath).toHaveBeenCalledWith("C:/AutoReview/Pipeline Review/outputs/runs/run_1/finding_traceability.csv");

    fireEvent.click(screen.getByText("Findings Review"));
    expect(screen.getByTitle("Filter by reviewer decision status. Rejected findings are excluded from default packets.")).toBeInTheDocument();
    expect(screen.getByTitle("Filter to findings flagged as possible RFIs or hide them while doing engineering QA triage.")).toBeInTheDocument();
    expect(await screen.findByText("Reviewer action", {}, { timeout: 3500 })).toBeInTheDocument();
    expect(screen.getByText("Alias sheets and client title-block variants can cause noise.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Accept"));
    await waitFor(() => expect(findings[0].status).toBe("Accepted"));
    fireEvent.change(screen.getByLabelText("Finding severity"), { target: { value: "Critical" } });
    fireEvent.change(screen.getByLabelText("Finding discipline"), { target: { value: "Document Control" } });
    fireEvent.change(screen.getByLabelText("Finding owner"), { target: { value: "Reviewer A" } });
    fireEvent.click(screen.getByLabelText("RFI candidate"));
    fireEvent.change(screen.getByLabelText("Edited packet comment"), { target: { value: "Reviewer-approved packet wording." } });
    fireEvent.change(screen.getByLabelText("Reviewer notes"), { target: { value: "Checked against drawing index and valve list." } });
    fireEvent.click(screen.getByText("Save Finding"));
    await waitFor(() => expect(findings[0].edited_message).toBe("Reviewer-approved packet wording."));
    expect(findings[0].owner).toBe("Reviewer A");
    expect(findings[0].rfi_candidate).toBe(true);

    fireEvent.click(screen.getByText("Possible duplicate sheet"));
    fireEvent.click(screen.getByText("Reject"));
    await waitFor(() => expect(findings[1].status).toBe("Rejected"));

    fireEvent.click(screen.getByText("Packet Export"));
    expect(screen.getByTitle("Choose packet contents: internal QA includes reviewer context, client review is cleaner, backcheck focuses unresolved/repeated items, and full debug includes diagnostics.")).toBeInTheDocument();
    expect(screen.getByTitle("Choose which findings enter the packet. Accepted-only is the default and excludes rejected false positives.")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("internal QA"), { target: { value: "client_review" } });
    fireEvent.click(screen.getByText("Export Packet"));
    expect(await screen.findByText(/Packet exported with 1 finding/)).toBeInTheDocument();
    expect(screen.getByText("C:/AutoReview/Pipeline Review/packets/single_review_packet.pdf")).toBeInTheDocument();
    const exportRequest = requests.find((request) => request.method === "POST" && request.path.endsWith("/export-packet"));
    expect(exportRequest?.body).toMatchObject({ packet_mode: "client_review", finding_scope: "accepted_only" });

    fireEvent.click(screen.getByText("Run History"));
    fireEvent.click(screen.getByText("Compare Latest Runs"));
    expect(await screen.findByText("status changed")).toBeInTheDocument();
    expect(screen.getByText("severity changed")).toBeInTheDocument();
    expect(screen.getByText("backcheck required")).toBeInTheDocument();
  });
});
