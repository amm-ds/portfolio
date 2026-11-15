import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FIXTURE_RUNS } from "../api/fixtures";
import { ComparisonCharts } from "./ComparisonCharts";

describe("model comparison charts", () => {
  it("scales cost to the largest displayed run instead of a one-dollar floor", () => {
    const runs = FIXTURE_RUNS.filter((run) => run.dataset_id === "support-routing-v1");
    const { container } = render(<ComparisonCharts runs={runs} />);

    const costRow = screen.getByRole("listitem", { name: "fixture-strict: $0.021" });
    expect(costRow.querySelector(".metric-chart__track span")).toHaveStyle({ width: "100%" });
    expect(screen.getByRole("listitem", { name: "fixture-fast: $0.006" }).querySelector(".metric-chart__track span")).toHaveStyle({ width: "28.57142857142857%" });
    expect(container.querySelectorAll(".metric-chart")).toHaveLength(4);
  });

  it("excludes incomplete runs instead of inventing metrics", () => {
    const runs = FIXTURE_RUNS.filter((run) => run.dataset_id === "support-routing-v1");
    render(<ComparisonCharts runs={[{ ...runs[0], status: "running", metrics: null }]} />);

    expect(screen.getByText("Nothing to compare")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
