import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { DemoManifest } from "../types";
import { DemoWorkbench } from "./DemoWorkbench";
import { KpiTile } from "./KpiTile";
import { Notice } from "./Notice";
import { useControlState } from "./useControlState";

/** Minimal manifest: two modes, one scenario, one live endpoint, one skill. */
const MANIFEST: DemoManifest = {
  id: "test-demo",
  title: "test demo",
  hook: "a hook line",
  project: "01-demo-project",
  group: "testing",
  skills: ["synthetic data"],
  modes: ["browser", "live"],
  hero: null,
  scenarios: [{ name: "base", controls: { ratio: 5 } }],
  live_endpoints: [
    { method: "POST", path: "/projects/01-demo-project/score", label: "scoring", cost: "free-local" },
  ],
  payload: { path: "reports/demo_payload.json", schema_version: 1, required_keys: [] },
};

/** Renders the workbench with a real control state, like a demo would. */
function Harness() {
  const state = useControlState({ ratio: 5 }, MANIFEST.scenarios);
  return (
    <MemoryRouter>
      <DemoWorkbench
        manifest={MANIFEST}
        state={state}
        kpis={
          <>
            <KpiTile label="alpha" value="1" />
            <KpiTile label="beta" value="2" />
            <Notice>the takeaway</Notice>
          </>
        }
        canvas={<div>canvas body</div>}
        controls={
          <div className="demo-control">
            <label htmlFor="ratio">ratio control</label>
            <input
              id="ratio"
              type="range"
              min={1}
              max={10}
              value={state.controls.ratio}
              onChange={() => undefined}
            />
          </div>
        }
        details={<div>secondary panels</div>}
        evidence={<p>method notes</p>}
      />
    </MemoryRouter>
  );
}

function renderWorkbench() {
  return render(<Harness />);
}

describe("DemoWorkbench", () => {
  it("renders the header with badges, scenario chips and actions", () => {
    renderWorkbench();
    expect(
      screen.getByRole("heading", { level: 1, name: "test demo" }),
    ).toBeInTheDocument();
    expect(screen.getByText("a hook line")).toBeInTheDocument();
    expect(screen.getByText("← demos")).toHaveAttribute("href", "/projects#demos");
    // mode badges + scenario chips
    expect(screen.getByText("in your browser")).toBeInTheDocument();
    expect(screen.getByText("live · free-local")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "base" })).toBeInTheDocument();
    // actions
    expect(screen.getByRole("button", { name: "copy link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "reset" })).toBeInTheDocument();
  });

  it("renders the KPI band with the tiles in order and the notice last", () => {
    renderWorkbench();
    const band = document.querySelector(".wb-kpi-band")!;
    expect(band).not.toBeNull();
    const labels = Array.from(band.querySelectorAll(".wb-kpi-label")).map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["alpha", "beta"]);
    expect(band.querySelector(".wb-notice")).not.toBeNull();
    expect(band.lastElementChild!.classList.contains("wb-notice")).toBe(true);
  });

  it("keeps the slider inside the fixed controls column", () => {
    renderWorkbench();
    const controls = document.querySelector(".wb-controls")!;
    expect(controls).not.toBeNull();
    const slider = controls.querySelector('input[type="range"]');
    expect(slider).not.toBeNull();
    expect(controls.querySelector(".wb-rail-title")!.textContent).toBe("controls");
  });

  it("opens the details band from a closed-by-default state", () => {
    renderWorkbench();
    const details = document.querySelector(".wb-details")!;
    expect(details).not.toBeNull();
    expect(details.hasAttribute("open")).toBe(false);
    fireEvent.click(screen.getByText("details"));
    expect(details.hasAttribute("open")).toBe(true);
    expect(details.querySelector(".wb-details-body")!.textContent).toContain(
      "secondary panels",
    );
  });

  it("gives the evidence drawer an internal-scroll body", () => {
    renderWorkbench();
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer).not.toBeNull();
    const body = drawer.querySelector(".wb-evidence-body")!;
    expect(body.classList.contains("wb-internal-scroll")).toBe(true);
    fireEvent.click(screen.getByText("evidence & provenance"));
    expect(drawer.hasAttribute("open")).toBe(true);
  });
});
