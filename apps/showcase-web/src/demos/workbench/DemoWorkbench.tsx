import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { DemoManifest } from "../types";
import type { ControlState } from "./useControlState";

/** Top-bar scenario chips; `active` is the scenario matching current controls. */
function ScenarioPicker({
  manifest,
  active,
  onApply,
}: {
  manifest: DemoManifest;
  active: string | null;
  onApply: (name: string) => void;
}) {
  if (manifest.scenarios.length === 0) return null;
  return (
    <div className="wb-scenarios" role="group" aria-label="scenarios">
      {manifest.scenarios.map((s) => (
        <button
          key={s.name}
          type="button"
          className={`chip wb-scenario${active === s.name ? " active" : ""}`}
          aria-pressed={active === s.name}
          onClick={() => onApply(s.name)}
        >
          {s.name}
        </button>
      ))}
    </div>
  );
}

/** Collapsible evidence drawer at the foot of the workbench. */
function EvidenceDrawer({
  manifest,
  about,
  children,
}: {
  manifest: DemoManifest;
  /** "How to interpret" content — rendered full width under the linked experiment. */
  about?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <details className="wb-evidence">
      <summary>Evidence & provenance</summary>
      <div className="wb-evidence-body wb-internal-scroll">
        <p className="wb-evidence-linked">
          <span className="wb-evidence-tag">linked experiment</span> →{" "}
          <Link to={`/projects/${manifest.project}`}>{manifest.project}</Link>
        </p>
        {about !== undefined && (
          <div className="wb-evidence-about">
            <h3 className="wb-evidence-tag">how to interpret</h3>
            {about}
          </div>
        )}
        <div className="wb-evidence-cols">{children}</div>
        {(manifest.skills.length > 0 || manifest.live_endpoints.length > 0) && (
          <div className="wb-evidence-chrome">
            {manifest.skills.length > 0 && (
              <div className="wb-skills">
                {manifest.skills.map((skill) => (
                  <span key={skill} className="chip">
                    {skill}
                  </span>
                ))}
              </div>
            )}
            {manifest.live_endpoints.length > 0 && (
              <div className="wb-endpoints">
                {manifest.live_endpoints.map((e) => (
                  <div key={`${e.method} ${e.path}`} className="wb-endpoint">
                    <span className={`wb-method wb-method-${e.method.toLowerCase()}`}>{e.method}</span>
                    <code>{e.path}</code>
                    <span className="wb-endpoint-label">{e.label}</span>
                    <span className="wb-endpoint-cost">{e.cost}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </details>
  );
}

/**
 * Shared chrome for a manifest-driven demo workbench.
 *
 * Usage pattern — the demo owns its control state and shares it between its
 * slots; `DemoWorkbench` renders chrome (header, KPI band, notice strip, main
 * row, secondary band, evidence drawer) around whatever each slot needs the
 * state for:
 *
 * ```tsx
 * const state = useControlState({ fn_ratio: 5, threshold: 0.175 }, manifest.scenarios);
 * return (
 *   <DemoWorkbench
 *     manifest={manifest}
 *     state={state}
 *     kpis={<KpiTiles state={state} payload={payload} />}
 *     canvas={<CostCurve state={state} payload={payload} />}
 *     controls={<FnSlider state={state} />}
 *     notice={<Notice>the takeaway…</Notice>}
 *     secondary={<SecondaryPanels payload={payload} />}
 *     evidence={<p>method notes…</p>}
 *   />
 * );
 * ```
 *
 * The root sizes to content (`height: auto`, `min-height: 100dvh`-ish): rows
 * hold their natural height and the page scrolls when the workbench exceeds
 * the viewport, so panels can be given real dimensions instead of shrinking
 * to fit a fixed screen.
 */
export function DemoWorkbench({
  manifest,
  state,
  kpis,
  canvas,
  controls,
  notice,
  secondary,
  under,
  evidence,
  about,
}: {
  manifest: DemoManifest;
  state: ControlState;
  /** KPI band content: KpiTiles only (the Notice renders in its own strip). */
  kpis: ReactNode;
  /** Dominant chart; sized to match the controls rail's natural height. */
  canvas: ReactNode;
  /** Investigation controls; fixed-width right column, sizes the main row. */
  controls: ReactNode;
  /** State-aware one-sentence takeaway; slim strip under the KPI band. */
  notice?: ReactNode;
  /** Secondary panels; always-visible band between the main row and the drawer. */
  secondary?: ReactNode;
  /** Optional full-width strip directly under the main row (below canvas +
   * controls), e.g. a horizontal scorer form. */
  under?: ReactNode;
  /** Extra content for the evidence drawer (method, caveats…). Demos can pass
   * two `.wb-evidence-col` blocks to lay it out in two columns. */
  evidence?: ReactNode;
  /** Optional "how to interpret" body for the collapsible under the header hook. */
  about?: ReactNode;
}) {
  // The rail sizes the main row with its natural content height; the chart is
  // set to the same explicit pixel height. CSS-only approaches loop here:
  // percentage heights against an auto row, or the measured SVG viewBox
  // feeding its intrinsic height back into layout, grow without bound.
  const controlsRef = useRef<HTMLElement | null>(null);
  const [railH, setRailH] = useState(0);
  useEffect(() => {
    const el = controlsRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const h = Math.round(el.getBoundingClientRect().height);
      setRailH((prev) => (Math.abs(prev - h) > 1 ? h : prev));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const canvasHeight = Math.max(400, railH) || undefined;

  return (
    <div className="wb-root">
      <header className="wb-header">
        <div className="wb-heading">
          <Link to="/projects#demos" className="demo-back wb-back">
            ← back to demos
          </Link>
          <h1 className="demo-title">{manifest.title}</h1>
          <p className="demo-hook">{manifest.hook}</p>
        </div>
        <div className="wb-actions">
          <ScenarioPicker
            manifest={manifest}
            active={state.activeScenario}
            onApply={state.applyScenario}
          />
          <button type="button" className="chip wb-reset" onClick={state.reset}>
            reset
          </button>
        </div>
      </header>

      <div className="wb-kpi-band">{kpis}</div>

      {notice !== undefined && <div className="wb-notice-strip">{notice}</div>}

      <div className="wb-main">
        <section className="wb-canvas-slot" style={{ height: canvasHeight }}>
          {canvas}
        </section>
        <aside className="wb-controls" ref={controlsRef}>
          <h2 className="wb-rail-title">controls</h2>
          {controls}
        </aside>
      </div>

      {under !== undefined && <div className="wb-under">{under}</div>}

      {secondary !== undefined && <div className="wb-secondary">{secondary}</div>}

      <EvidenceDrawer manifest={manifest} about={about}>
        {evidence}
      </EvidenceDrawer>
    </div>
  );
}
