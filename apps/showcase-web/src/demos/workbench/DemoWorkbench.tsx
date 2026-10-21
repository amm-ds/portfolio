import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { DemoManifest } from "../types";
import type { ControlState } from "./useControlState";

const MODE_LABELS: Record<string, string> = {
  browser: "in your browser",
  live: "live",
  replay: "replay",
};

function ModeBadge({ mode, manifest }: { mode: string; manifest: DemoManifest }) {
  const cost = manifest.live_endpoints.find((e) => e.method === "POST")?.cost;
  return (
    <span className="chip wb-mode" data-mode={mode}>
      {MODE_LABELS[mode] ?? mode}
      {mode === "live" && cost ? ` · ${cost}` : ""}
    </span>
  );
}

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

/** Collapsible evidence drawer below the workbench body. */
function EvidenceDrawer({
  manifest,
  children,
}: {
  manifest: DemoManifest;
  children?: ReactNode;
}) {
  return (
    <details className="wb-evidence">
      <summary>evidence & provenance</summary>
      <div className="wb-evidence-body">
        <p className="wb-evidence-line">
          linked experiment → <Link to={`/projects/${manifest.project}`}>{manifest.project}</Link>
        </p>
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
        {children}
      </div>
    </details>
  );
}

/**
 * Shared chrome for a manifest-driven demo workbench.
 *
 * Usage pattern — the demo owns its control state and shares it between its
 * slots; `DemoWorkbench` renders chrome (top bar, rails, evidence drawer)
 * around whatever each slot needs the state for:
 *
 * ```tsx
 * const state = useControlState({ fn_ratio: 5, threshold: 0.175 }, manifest.scenarios);
 * return (
 *   <DemoWorkbench
 *     manifest={manifest}
 *     state={state}
 *     controls={<FnSlider state={state} />}
 *     canvas={<CostCurve state={state} payload={payload} />}
 *     insight={<KpiTiles state={state} payload={payload} />}
 *     evidence={<p>method notes…</p>}
 *   />
 * );
 * ```
 */
export function DemoWorkbench({
  manifest,
  state,
  controls,
  canvas,
  insight,
  evidence,
}: {
  manifest: DemoManifest;
  state: ControlState;
  /** Left control rail content (state consumers). */
  controls: ReactNode;
  /** Center canvas content. */
  canvas: ReactNode;
  /** Right insight rail content (KPIs, notice). */
  insight: ReactNode;
  /** Extra content for the evidence drawer (method, caveats…). */
  evidence?: ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const share = () => {
    const url = state.shareUrl;
    const done = () => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).then(done, () => window.prompt("copy demo link", url));
    } else {
      window.prompt("copy demo link", url);
    }
  };

  return (
    <div className="wb-shell">
      <nav className="demo-topbar">
        <Link to="/projects#demos" className="demo-back">
          ← demos
        </Link>
      </nav>
      <header className="wb-header">
        <div className="wb-heading">
          <h1 className="demo-title">{manifest.title}</h1>
          <p className="demo-hook">{manifest.hook}</p>
        </div>
        <div className="wb-actions">
          <div className="wb-modes">
            {manifest.modes.map((mode) => (
              <ModeBadge key={mode} mode={mode} manifest={manifest} />
            ))}
          </div>
          <ScenarioPicker
            manifest={manifest}
            active={state.activeScenario}
            onApply={state.applyScenario}
          />
          <div className="wb-buttons">
            <button type="button" className="chip wb-share" onClick={share}>
              {copied ? "copied ✓" : "copy link"}
            </button>
            <button type="button" className="chip wb-reset" onClick={state.reset}>
              reset
            </button>
          </div>
        </div>
      </header>

      <div className="wb-body">
        <aside className="wb-rail wb-rail-controls">
          <h2 className="wb-rail-title">controls</h2>
          {controls}
        </aside>
        <section className="wb-canvas">{canvas}</section>
        <aside className="wb-rail wb-rail-insight">
          <h2 className="wb-rail-title">readout</h2>
          {insight}
        </aside>
      </div>

      <EvidenceDrawer manifest={manifest}>{evidence}</EvidenceDrawer>
    </div>
  );
}
