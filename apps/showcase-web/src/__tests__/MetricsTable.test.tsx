import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricsTable } from "../components/MetricsTable";

describe("MetricsTable", () => {
  it("renders runs as rows and metrics as columns", () => {
    render(
      <MetricsTable
        metrics={{
          baseline: { f1: 0.5, precision: 0.7 },
          fine_tuned: { f1: 0.812345, precision: 0.876543 },
        }}
      />,
    );
    expect(screen.getByText("baseline")).toBeInTheDocument();
    expect(screen.getByText("fine_tuned")).toBeInTheDocument();
    expect(screen.getByText("f1")).toBeInTheDocument();
    expect(screen.getByText("0.5000")).toBeInTheDocument();
    expect(screen.getByText("0.8123")).toBeInTheDocument();
  });

  it("renders a dash for missing metric values", () => {
    render(<MetricsTable metrics={{ run_a: { f1: 0.9 }, run_b: { accuracy: 0.95 } }} />);
    const row = screen.getByText("run_b").closest("tr");
    expect(row).not.toBeNull();
    expect(row!.querySelectorAll("td")[1]).toHaveTextContent("—");
  });

  it("renders nothing for empty metrics", () => {
    const { container } = render(<MetricsTable metrics={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it("tolerates a nested _meta key without crashing", () => {
    render(
      <MetricsTable
        metrics={{
          gbm: { mae: 4.67 },
          _meta: { split: "temporal holdout", mae_ranking: ["gbm", "nn"], p90_coverage: 0.91 },
        }}
      />,
    );
    expect(screen.getByText("gbm")).toBeInTheDocument();
    expect(screen.queryByText("_meta")).not.toBeInTheDocument();
    expect(screen.getByText(/split: temporal holdout/)).toBeInTheDocument();
    expect(screen.getByText(/p90_coverage: 0.9100/)).toBeInTheDocument();
  });
});
