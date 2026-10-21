import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { DemoManifest } from "../types";
import { DemoWorkbench } from "./DemoWorkbench";
import { KpiTile } from "./KpiTile";
import { Notice } from "./Notice";
import { useControlState } from "./useControlState";

/** Minimal manifest: one scenario, one live endpoint, one skill. */
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
            <KpiTile label="gamma" value="3" />
            <KpiTile label="delta" value="4" />
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
        notice={<Notice>the takeaway</Notice>}
        under={<div className="wb-under-content">under strip</div>}
        secondary={
          <>
            <div className="wb-secondary-panel">
              <h3 className="wb-rail-title">panel one</h3>
              <div>first panel</div>
            </div>
            <div className="wb-secondary-panel">
              <h3 className="wb-rail-title">panel two</h3>
              <div>second panel</div>
            </div>
            <div className="wb-secondary-panel">
              <h3 className="wb-rail-title">panel three</h3>
              <div>third panel</div>
            </div>
          </>
        }
        evidence={<p>method notes</p>}
      />
    </MemoryRouter>
  );
}

function renderWorkbench() {
  return render(<Harness />);
}

describe("DemoWorkbench", () => {
  it("renders a small back link above the title, then the title and hook summary", () => {
    renderWorkbench();
    const back = screen.getByRole("link", { name: "← back to demos" });
    expect(back).toHaveAttribute("href", "/projects#demos");
    // back link sits in the heading, before the title — never beside it
    const heading = document.querySelector(".wb-heading")!;
    expect(heading.firstElementChild).toBe(back);
    const title = screen.getByRole("heading", { level: 1, name: "test demo" });
    expect(back.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // hook renders as the muted summary paragraph under the title
    const summary = document.querySelector(".wb-heading .demo-hook")!;
    expect(summary.textContent).toContain("a hook line");
    // the dropped chrome stays gone: no mode badges, no copy-link button
    expect(screen.queryByText("in your browser")).toBeNull();
    expect(screen.queryByText(/live · free-local/)).toBeNull();
    expect(screen.queryByRole("button", { name: "copy link" })).toBeNull();
  });

  it("keeps only the reset action in the header (scenarios live in URL state)", () => {
    renderWorkbench();
    expect(screen.getByRole("button", { name: "reset" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "base" })).toBeNull();
  });

  it("renders the KPI band with exactly the four tiles, no notice inside", () => {
    renderWorkbench();
    const band = document.querySelector(".wb-kpi-band")!;
    expect(band).not.toBeNull();
    const labels = Array.from(band.querySelectorAll(".wb-kpi-label")).map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["alpha", "beta", "gamma", "delta"]);
    expect(band.querySelectorAll(".wb-kpi")).toHaveLength(4);
    expect(band.querySelector(".wb-notice")).toBeNull();
  });

  it("renders the notice as a slim strip directly under the KPI band", () => {
    renderWorkbench();
    const strip = document.querySelector(".wb-notice-strip")!;
    expect(strip).not.toBeNull();
    expect(strip.textContent).toContain("the takeaway");
    const root = document.querySelector(".wb-root")!;
    const band = root.querySelector(".wb-kpi-band")!;
    expect(
      band.compareDocumentPosition(strip) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps the slider inside the fixed controls column", () => {
    renderWorkbench();
    const controls = document.querySelector(".wb-controls")!;
    expect(controls).not.toBeNull();
    const slider = controls.querySelector('input[type="range"]');
    expect(slider).not.toBeNull();
    expect(controls.querySelector(".wb-rail-title")!.textContent).toBe("controls");
  });

  it("renders the secondary band always-visible with three panels (no details toggle)", () => {
    renderWorkbench();
    const band = document.querySelector(".wb-secondary")!;
    expect(band).not.toBeNull();
    const panels = band.querySelectorAll(".wb-secondary-panel");
    expect(panels).toHaveLength(3);
    expect(band.textContent).toContain("first panel");
    expect(band.textContent).toContain("second panel");
    expect(band.textContent).toContain("third panel");
    // panel headers are CAPITALS rail titles
    const titles = Array.from(band.querySelectorAll(".wb-rail-title")).map(
      (el) => el.textContent,
    );
    expect(titles).toEqual(["panel one", "panel two", "panel three"]);
    // the old collapsible details element is gone
    expect(document.querySelector(".wb-details")).toBeNull();
    expect(screen.queryByText("details")).toBeNull();
  });

  it("renders the optional under strip below the main row when provided", () => {
    renderWorkbench();
    const root = document.querySelector(".wb-root")!;
    const under = root.querySelector(".wb-under")!;
    expect(under.textContent).toContain("under strip");
    // sits after the canvas slot, before the secondary band
    const canvas = root.querySelector(".wb-canvas-slot")!;
    const band = root.querySelector(".wb-secondary")!;
    expect(
      canvas.compareDocumentPosition(under) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(under.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("gives the evidence drawer an internal-scroll body", () => {
    renderWorkbench();
    const drawer = document.querySelector(".wb-evidence")!;
    expect(drawer).not.toBeNull();
    const body = drawer.querySelector(".wb-evidence-body")!;
    expect(body.classList.contains("wb-internal-scroll")).toBe(true);
  });
});
