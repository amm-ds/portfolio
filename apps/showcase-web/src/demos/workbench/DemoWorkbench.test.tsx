import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { DemoManifest } from "../types";
import { DemoWorkbench } from "./DemoWorkbench";
import { KpiTile } from "./KpiTile";
import { Notice } from "./Notice";
import { useControlState } from "./useControlState";

/** Minimal manifest: two scenarios, one live endpoint, one skill, one hero. */
const MANIFEST: DemoManifest = {
  id: "test-demo",
  title: "test demo",
  hook: "a hook line",
  project: "01-demo-project",
  group: "testing",
  skills: ["synthetic data"],
  modes: ["browser", "live"],
  hero: {
    label: "headline metric",
    value: "1.23 vs 4.56",
    ci: "paired bootstrap CI [−0.3, −0.1]",
  },
  scenarios: [
    { name: "base", controls: { ratio: 5 } },
    { name: "wide", controls: { ratio: 9 } },
  ],
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

  it("renders the manifest hero as a concise strip under the hook", () => {
    renderWorkbench();
    const hero = document.querySelector(".wb-hero")!;
    expect(hero).not.toBeNull();
    expect(hero.textContent).toContain("headline metric");
    expect(hero.textContent).toContain("1.23 vs 4.56");
    expect(hero.textContent).toContain("paired bootstrap CI [−0.3, −0.1]");
    // sits inside the heading, after the hook
    const heading = document.querySelector(".wb-heading")!;
    const hook = heading.querySelector(".demo-hook")!;
    expect(
      hook.compareDocumentPosition(hero) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders manifest scenarios as chips in the header and applies them", () => {
    renderWorkbench();
    const base = screen.getByRole("button", { name: "base" });
    const wide = screen.getByRole("button", { name: "wide" });
    for (const chip of [base, wide]) {
      expect(chip.classList.contains("wb-scenario")).toBe(true);
    }
    // controls start at the defaults -> the matching scenario is active
    expect(base.getAttribute("aria-pressed")).toBe("true");
    expect(wide.getAttribute("aria-pressed")).toBe("false");
    expect(base.classList.contains("active")).toBe(true);
    // applying a scenario pushes its controls through the shared state
    fireEvent.click(wide);
    expect(wide.classList.contains("active")).toBe(true);
    expect(base.getAttribute("aria-pressed")).toBe("false");
    const slider = screen.getByLabelText("ratio control") as HTMLInputElement;
    expect(slider.value).toBe("9");
    // reset restores the defaults and re-activates the base scenario
    fireEvent.click(screen.getByRole("button", { name: "reset" }));
    expect(base.classList.contains("active")).toBe(true);
    expect(slider.value).toBe("5");
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

  it("renders more information under the header with the two-column body", () => {
    renderWorkbench();
    const more = document.querySelector(".wb-more")!;
    expect(more).not.toBeNull();
    expect(more.querySelector("summary")!.textContent).toContain("more information");
    expect(more.querySelectorAll(".wb-evidence-col")).toHaveLength(2);
    expect(more.querySelector(".wb-evidence-cols")).not.toBeNull();
  });

  it("lists live endpoints with method, path, label and cost in the drawer footer", () => {
    renderWorkbench();
    const more = document.querySelector(".wb-more")!;
    const endpoints = more.querySelector(".wb-endpoints")!;
    expect(endpoints).not.toBeNull();
    const row = endpoints.querySelector(".wb-endpoint")!;
    expect(row.querySelector(".wb-method")!.textContent).toBe("POST");
    expect(row.querySelector(".wb-method-post")).not.toBeNull();
    expect(row.querySelector("code")!.textContent).toBe("/projects/01-demo-project/score");
    expect(row.querySelector(".wb-endpoint-label")!.textContent).toBe("scoring");
    expect(row.querySelector(".wb-endpoint-cost")!.textContent).toBe("free-local");
    // the endpoint block sits in the chrome footer, next to the skills chips
    const chrome = more.querySelector(".wb-evidence-chrome")!;
    expect(chrome.contains(endpoints)).toBe(true);
    expect(chrome.querySelector(".wb-skills")).not.toBeNull();
  });
});
