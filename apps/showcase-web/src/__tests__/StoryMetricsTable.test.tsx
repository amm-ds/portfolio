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

  it("renders a delta for EVERY candidate row vs the baseline", () => {
    render(
      <StoryMetricsTable
        metrics={{
          naive_last: { mae: 100 },
          model_a: { mae: 80 },
          model_b: { mae: 60 },
        }}
        metricsKeys={["naive_last", "model_a", "model_b"]}
      />,
    );
    expect(screen.getByText(/-40% vs naive_last/)).toBeInTheDocument();
    expect(screen.getByText(/-20% vs naive_last/)).toBeInTheDocument();
    // the baseline row itself still shows the em dash
    const baselineRow = screen.getByText("naive_last").closest("tr")!;
    expect(baselineRow).toHaveTextContent("—");
  });

  it("shows an em dash for a row whose metric cannot be compared against the baseline", () => {
    render(
      <StoryMetricsTable
        metrics={{
          naive_last: { mae: 0, rmse: 100 },
          model_a: { mae: 5 },
          model_b: { rmse: 80 },
        }}
        metricsKeys={["naive_last", "model_a", "model_b"]}
      />,
    );
    // model_a's mae baseline is 0 → no comparable delta; model_b compares fine
    const rowA = screen.getByText("model_a").closest("tr")!;
    expect(rowA).toHaveTextContent("—");
    const rowB = screen.getByText("model_b").closest("tr")!;
    expect(rowB).toHaveTextContent(/-20% vs naive_last/);
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
