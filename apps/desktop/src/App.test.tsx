import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const responses: Record<string, unknown> = {
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

describe("AutoReview desktop shell", () => {
  beforeEach(() => {
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
});
