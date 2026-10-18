import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StoryMetricsTable } from "../components/StoryMetricsTable";

const METRICS = {
  naive_last: { faithfulness: 0.5 },
  tuned: { faithfulness: 0.75 },
};

describe("StoryMetricsTable", () => {
  it("renders a row per referenced run with its headline metric and value", () => {
    render(<StoryMetricsTable metrics={METRICS} metricsKeys={["naive_last", "tuned"]} />);
    for (const run of ["naive_last", "tuned"]) {
      const row = screen.getByText(run).closest("tr");
      expect(row).not.toBeNull();
      expect(row!).toHaveTextContent("faithfulness");
    }
    expect(screen.getByText("0.5000")).toBeInTheDocument();
    expect(screen.getByText("0.7500")).toBeInTheDocument();
  });

  it("formats integers without decimals", () => {
    render(
      <StoryMetricsTable
        metrics={{ run_a: { business_cost: 601 } }}
        metricsKeys={["run_a"]}
      />,
    );
    expect(screen.getByText("601")).toBeInTheDocument();
  });

  it("renders a delta column with signed pct vs baseline when one applies", () => {
    render(<StoryMetricsTable metrics={METRICS} metricsKeys={["naive_last", "tuned"]} />);
    expect(screen.getByText("Δ vs baseline")).toBeInTheDocument();
    const delta = screen.getByText(/\+50% vs naive_last/);
    expect(delta).toBeInTheDocument();
    expect(delta.classList.contains("improved")).toBe(true);
    // baseline row itself carries no delta
    const baselineRow = screen.getByText("naive_last").closest("tr")!;
    expect(baselineRow).toHaveTextContent("—");
  });

  it("marks a negative delta as improved for lower-is-better metrics", () => {
    render(
      <StoryMetricsTable
        metrics={{ naive_last: { mae: 0.4 }, tuned: { mae: 0.3 } }}
        metricsKeys={["naive_last", "tuned"]}
      />,
    );
    const delta = screen.getByText(/-25% vs naive_last/);
    expect(delta.classList.contains("improved")).toBe(true);
  });

  it("omits the delta column when no baseline applies", () => {
    render(
      <StoryMetricsTable
        metrics={{ run_a: { f1: 0.9 }, run_b: { f1: 0.8 } }}
        metricsKeys={["run_a", "run_b"]}
      />,
    );
    expect(screen.queryByText("Δ vs baseline")).toBeNull();
  });

  it("renders nothing without metrics_keys", () => {
    const { container } = render(<StoryMetricsTable metrics={METRICS} metricsKeys={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when no referenced run has metrics", () => {
    const { container } = render(
      <StoryMetricsTable metrics={METRICS} metricsKeys={["missing_run"]} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
