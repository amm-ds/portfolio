import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { FIXTURE_DATASETS, FIXTURE_RUNS } from "./api/fixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/datasets") return jsonResponse(FIXTURE_DATASETS);
      if (url === "/runs") return jsonResponse(FIXTURE_RUNS);
      if (url.startsWith("/runs/")) {
        const run = FIXTURE_RUNS.find((item) => item.id === decodeURIComponent(url.slice(6)));
        return run ? jsonResponse(run) : jsonResponse({ detail: "Not found" }, 404);
      }
      throw new Error(`Unexpected URL: ${url}`);
    }),
  );
}

describe("evaluation workbench", () => {
  it("loads the registry, selected run, and same-dataset comparison", async () => {
    stubApi();
    render(<App />);

    expect(screen.getByText("Loading datasets…")).toBeInTheDocument();
    expect(await screen.findByText("case-billing")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Support routing" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evaluation runs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Model comparison" })).toBeInTheDocument();
    expect(screen.getByText("4 inspected · 1 incorrect · 0 execution failures")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem", { name: /fixture-/ })).toHaveLength(12);
    expect(screen.getByText("API connected")).toBeInTheDocument();
  });

  it("switches dataset versions and replaces the run detail and comparison", async () => {
    stubApi();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("case-billing");

    await user.click(screen.getByRole("button", { name: /Refusal probes/ }));

    expect(await screen.findByText("probe-secret")).toBeInTheDocument();
    expect(screen.queryByText("case-billing")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Refusal probes" })).toBeInTheDocument();
    expect(screen.getByText("3 inspected · 1 incorrect · 0 execution failures")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Exact values for every completed run in this comparison" })).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Exact values for every completed run in this comparison" })).getAllByRole("row")).toHaveLength(2);
  });

  it("filters a run to incorrect and failed cases", async () => {
    stubApi();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("case-billing");

    await user.click(screen.getByRole("button", { name: "Needs review" }));

    expect(screen.getByText("case-outage")).toBeInTheDocument();
    expect(screen.queryByText("case-billing")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Needs review" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("case-billing")).toBeInTheDocument();
  });

  it("surfaces network failures without rendering fabricated records", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the eval-workbench API.");
    expect(screen.getByText("API unavailable")).toBeInTheDocument();
    expect(screen.getByText("No datasets registered.")).toBeInTheDocument();
    expect(screen.getByText("No dataset selected")).toBeInTheDocument();
  });

  it("keeps theme controls accessible", async () => {
    stubApi();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("case-billing");

    const light = screen.getByRole("button", { name: "light" });
    expect(screen.getByRole("button", { name: "dark" })).toHaveAttribute("aria-pressed", "true");
    await user.click(light);
    expect(light).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
