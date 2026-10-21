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

/** Collapsible details band between the main row and the evidence drawer. */
function DetailsBand({ children }: { children?: ReactNode }) {
  return (
    <details className="wb-details">
      <summary>details</summary>
      <div className="wb-details-body wb-internal-scroll">{children}</div>
    </details>
  );
}

/** Collapsible evidence drawer at the foot of the workbench. */
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
      <div className="wb-evidence-body wb-internal-scroll">
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
 * slots; `DemoWorkbench` renders chrome (header, KPI band, main row, details
 * band, evidence drawer) around whatever each slot needs the state for:
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
 *     details={<SecondaryPanels payload={payload} />}
 *     evidence={<p>method notes…</p>}
 *   />
 * );
 * ```
 *
 * The root is a fixed-height (100dvh) grid: opening the details band or the
 * evidence drawer steals space from the `minmax(0, 1fr)` chart row instead of
 * growing the page, so the workbench never scrolls at desktop widths.
 */
export function DemoWorkbench({
  manifest,
  state,
  kpis,
  canvas,
  controls,
  details,
  evidence,
}: {
  manifest: DemoManifest;
  state: ControlState;
  /** KPI band content: KpiTiles + (last) Notice. */
  kpis: ReactNode;
  /** Dominant chart; flex-grows to fill the main row. */
  canvas: ReactNode;
  /** Investigation controls; fixed-width right column. */
  controls: ReactNode;
  /** Secondary panels shown in the collapsible details band. */
  details?: ReactNode;
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
    <div className="wb-root">
      <header className="wb-header">
        <nav className="demo-topbar">
          <Link to="/projects#demos" className="demo-back">
            ← demos
          </Link>
        </nav>
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

      <div className="wb-kpi-band">{kpis}</div>

      <div className="wb-main">
        <section className="wb-canvas-slot">{canvas}</section>
        <aside className="wb-controls">
          <h2 className="wb-rail-title">controls</h2>
          {controls}
        </aside>
      </div>

      {details !== undefined && <DetailsBand>{details}</DetailsBand>}

      <EvidenceDrawer manifest={manifest}>{evidence}</EvidenceDrawer>
    </div>
  );
}
