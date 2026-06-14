import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

let responses: Record<string, unknown>;

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

describe("AutoReview desktop shell", () => {
  beforeEach(() => {
    responses = baseResponses();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const body = responses[url.pathname] ?? {};
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
    expect(screen.getByText("Drawing Index Reconciliation")).toBeInTheDocument();
    expect(screen.getByText("fingerprint123")).toBeInTheDocument();
    expect(screen.getByText("Draft -> Accepted")).toBeInTheDocument();
  });
});
