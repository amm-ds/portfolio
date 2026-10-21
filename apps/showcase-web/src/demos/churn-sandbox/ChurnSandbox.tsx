import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { CalibrationScatter } from "../charts/CalibrationScatter";
import { LineChart, type LineMarker } from "../charts/LineChart";
import { SegmentLegend, type HBarSegment } from "../charts/StackedHBar";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { ChurnPayload, ConfusionRow, DemoManifest } from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import { contactCount, costAt, nearestIndex, noticeText, optimalityText, recallAt, savings } from "./kpis";
import { CostCompositionPanel } from "./CostCompositionPanel";
import { fetchChurnPayload, fetchManifest } from "./payload";
import { ScorerCard } from "./ScorerCard";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

/** A customer pinned on the cost curve: label (short form) + scored probability. */
interface CustomerMarker {
  label: string;
  probability: number;
}

/** Short form of a preset label for chart annotation ("at-risk fiber customer" → "at-risk fiber"). */
function shortLabel(label: string): string {
  return label.split(" ").slice(0, 2).join(" ");
}

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "churn-sandbox",
  title: "churn threshold sandbox",
  hook: "Move the alarm threshold and the missed-churner cost — watch the optimal cutoff and the saved budget change on a real churn model.",
  project: "05-ml-pipeline-churn",
  group: "retain customers",
  skills: ["classification economics", "calibration", "decision science"],
  modes: ["browser", "live"],
  hero: {
    label: "decision cost per 1,400 customers",
    value: "$601 vs $1,035 naive",
    ci: "paired bootstrap CI [−485, −343]",
  },
  scenarios: [
    { name: "base", controls: { fn_ratio: 5, threshold: 0.175 } },
    { name: "high-cost-miss", controls: { fn_ratio: 9, threshold: 0.12 } },
    { name: "default-threshold", controls: { fn_ratio: 5, threshold: 0.5 } },
  ],
  live_endpoints: [
    { method: "POST", path: "/projects/05-ml-pipeline-churn/score", label: "live customer scoring", cost: "free-local" },
  ],
  payload: { path: "reports/demo_payload.json", schema_version: 1, required_keys: [] },
};

/** Card with the shared figure-card chrome (chart region + commentary band). */
function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      <div className="demo-chart">{children}</div>
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

// --- cost curve panel ------------------------------------------------------------

function CostCurvePanel({
  payload,
  fnRatio,
  cursorIdx,
  customer,
  onCursor,
}: {
  payload: ChurnPayload;
  fnRatio: number;
  cursorIdx: number;
  customer: CustomerMarker | null;
  onCursor: (idx: number) => void;
}) {
  const { thresholds, overall, model } = payload;
  const costs = overall.map((r) => costAt(r, fnRatio));
  const defaultIdx = nearestIndex(thresholds, model.threshold_default);
  const selectedIdx = nearestIndex(thresholds, model.threshold_selected);

  const cursorT = thresholds[cursorIdx];
  const cursorCost = costs[cursorIdx];
  const defaultCost = costs[defaultIdx];
  const delta = cursorCost - defaultCost;
  const cursorRow = overall[cursorIdx];

  const markers: LineMarker[] = [
    { xIndex: defaultIdx, label: "default 0.5", style: "dashed" },
    { xIndex: selectedIdx, style: "star" },
  ];
  if (customer) {
    markers.push({
      xIndex: nearestIndex(thresholds, customer.probability),
      label: customer.label,
      style: "solid",
      color: customer.probability >= cursorT ? C_TEAL : C_GRAY,
    });
  }

  return (
    <Figure
      comment={
        <>
          Cost = FP + N×FN on the untouched holdout; drag the cursor and the curve refits
          when the multiplier changes — the star marks the threshold the pipeline committed to.
        </>
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">threshold t = {cursorT.toFixed(2)}</span>
        <span className="chip demo-readout">cost at t: {Math.round(cursorCost)}</span>
        <span className="chip demo-readout">cost at 0.5: {Math.round(defaultCost)}</span>
        <span className={`chip demo-readout ${delta < 0 ? "good" : "bad"}`}>
          {delta < 0 ? "saves" : "costs"} {Math.abs(Math.round(delta))} vs 0.5
        </span>
        <span className="chip demo-readout">
          contact {cursorRow.fp + cursorRow.tp} of {payload.holdout_n}
        </span>
      </div>
      <LineChart
        x={thresholds}
        series={[{ name: "cost", color: C_TEAL, values: costs }]}
        cursor={cursorIdx}
        onCursorChange={onCursor}
        markers={markers}
        ariaLabel="campaign cost over alarm threshold"
      />
      <p className="demo-hint">drag the chart to move the threshold</p>
    </Figure>
  );
}

// --- decision outcomes panel ------------------------------------------------------

function OutcomesPanel({ row, holdoutN }: { row: ConfusionRow; holdoutN: number }) {
  // fill the panel box: measure the wrapper and draw the bar on a matching
  // viewBox (same pattern as the cost-composition panel)
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 90;
  const perK = (v: number) => Math.round((v * 1000) / holdoutN);
  const segments: HBarSegment[] = [
    { label: "TP", value: perK(row.tp), color: C_TEAL },
    { label: "FP", value: perK(row.fp), color: C_AMBER },
    { label: "FN", value: perK(row.fn), color: C_PINK },
    { label: "TN", value: perK(row.tn), color: C_GRAY },
  ];
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  let x = 0;
  return (
    <Figure
      comment={
        <>
          The pink slice is churners the campaign misses at the cursor; every amber contact
          is a customer who would have stayed anyway.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="outcome mix at the cursor threshold"
        >
          {segments.map((s) => {
            const w = (s.value / total) * W;
            const rect = (
              <rect
                key={s.label}
                x={x.toFixed(1)}
                y={0}
                width={Math.max(w, 0).toFixed(1)}
                height={H}
                fill={s.color}
              >
                <title>{`${s.label}: ${s.value}`}</title>
              </rect>
            );
            x += w;
            return rect;
          })}
        </svg>
      </div>
      <SegmentLegend segments={segments} />
      <p className="demo-hint">
        confusion-matrix counts at t = {row.t.toFixed(2)}, normalized per 1,000 customers
      </p>
    </Figure>
  );
}

// --- contract slices panel ----------------------------------------------------------

function SlicesPanel({ slices, cursorT }: { slices: Record<string, ConfusionRow[]>; cursorT: number }) {
  // container-measured like the other panels: the bars fill the whole box
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 90;
  const rows = Object.entries(slices).map(([label, rowsForSlice]) => {
    const row = rowsForSlice[nearestIndex(rowsForSlice.map((r) => r.t), cursorT)];
    return { label, value: row.tp + row.fp, unit: "alarms" };
  });
  const max = Math.max(...rows.map((r) => r.value), 1);
  const labelW = Math.min(120, W * 0.35);
  const countW = 64;
  const barX = labelW + 8;
  const barW = Math.max(W - barX - countW - 8, 0);
  const rowH = rows.length > 0 ? H / rows.length : H;
  return (
    <Figure
      comment={
        <>
          Alarm burden by contract at the cursor — most of it lands on month-to-month
          customers, who churn the most and dominate the contact list.
        </>
      }
    >
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="alarm burden by contract"
        >
          {rows.map((r, i) => {
            const cy = rowH * i + rowH / 2;
            const w = (r.value / max) * barW;
            return (
              <g key={r.label}>
                <text x={0} y={cy + 3} className="demo-axis-label">
                  {r.label}
                </text>
                <rect
                  x={barX}
                  y={cy - 7}
                  width={barW}
                  height={14}
                  fill="var(--bg)"
                  stroke="var(--border)"
                />
                <rect
                  x={barX}
                  y={cy - 7}
                  width={w}
                  height={14}
                  fill="var(--accent)"
                  opacity={0.8}
                />
                <text x={W} y={cy + 3} textAnchor="end" className="demo-axis-label">
                  {r.value} {r.unit}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Figure>
  );
}

// --- demo ------------------------------------------------------------------------------

export default function ChurnSandbox() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<ChurnPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchManifest("churn-sandbox")
      .then((m) => !cancelled && setManifest(m))
      .catch(() => {
        /* payload fetch below reports the real error */
      });
    fetchChurnPayload("churn-sandbox")
      .then((p) => !cancelled && setPayload(p))
      .catch(() => !cancelled && setError("could not load the demo payload — is the API running?"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <div className="state-box error">{error}</div>;
  }
  if (payload === null) {
    return <p className="loading">loading demo…</p>;
  }
  return <ChurnSandboxWorkbench manifest={manifest ?? FALLBACK_MANIFEST} payload={payload} />;
}

/** Workbench body once the payload (and manifest, or fallback) is in hand. */
function ChurnSandboxWorkbench({
  manifest,
  payload,
}: {
  manifest: DemoManifest;
  payload: ChurnPayload;
}) {
  const state = useControlState(
    { fn_ratio: payload.cost_model.fn_cost, threshold: payload.model.threshold_selected },
    manifest.scenarios,
  );
  const { controls, setControl } = state;
  const fnRatio = controls.fn_ratio ?? payload.cost_model.fn_cost;

  // scorer form pre-filled with the first preset (old sandbox behavior)
  const [form, setForm] = useState<Record<string, number | string> | null>(() => ({
    ...payload.customers[0].features,
  }));
  const [presetKey, setPresetKey] = useState(0);
  // customer pinned on the cost curve: set by preset chips and live scores
  const [customer, setCustomer] = useState<CustomerMarker | null>(null);

  const cursorIdx = nearestIndex(payload.thresholds, controls.threshold);
  const cursorT = payload.thresholds[cursorIdx];
  const cursorRow = payload.overall[cursorIdx];
  const defaultRow = payload.overall[nearestIndex(payload.thresholds, payload.model.threshold_default)];
  const laxerRow = cursorIdx > 0 ? payload.overall[cursorIdx - 1] : null;
  const { delta_ci } = payload.headline;
  const saved = savings(cursorRow, defaultRow, fnRatio);

  const moveCursor = (idx: number) => setControl("threshold", payload.thresholds[idx]);

  /** Label a live-scored probability with its nearest preset band. */
  const nearestPresetLabel = (probability: number) =>
    shortLabel(
      payload.customers.reduce((best, c) =>
        Math.abs(c.churn_probability - probability) < Math.abs(best.churn_probability - probability)
          ? c
          : best,
      ).label,
    );

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="fn-ratio">
              FP/FN cost ratio
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="fn-ratio"
                  type="range"
                  className="wb-slider"
                  min={1}
                  max={10}
                  step={1}
                  value={fnRatio}
                  style={{ "--fill": `${((fnRatio - 1) / 9) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("fn_ratio", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{fnRatio}×</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-presets">
            <span className="wb-rail-title">Preset customers</span>
            <div className="demo-control">
              <div className="demo-presets">
                {payload.customers.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    className="chip demo-preset"
                    onClick={() => {
                      setForm({ ...c.features });
                      setPresetKey((k) => k + 1);
                      setCustomer({ label: shortLabel(c.label), probability: c.churn_probability });
                    }}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {form !== null && (
            <div className="wb-control-group wb-group-scorer">
              <span className="wb-rail-title">Score a customer</span>
              <ScorerCard
                key={presetKey}
                payload={payload}
                cursorT={cursorT}
                form={form}
                setForm={setForm}
                onScore={(probability) =>
                  setCustomer({ label: nearestPresetLabel(probability), probability })
                }
              />
            </div>
          )}
        </>
      }
      canvas={
        <CostCurvePanel
          payload={payload}
          fnRatio={fnRatio}
          cursorIdx={cursorIdx}
          customer={customer}
          onCursor={moveCursor}
        />
      }
      kpis={
        <>
          <KpiTile
            label="cost at t"
            value={String(Math.round(costAt(cursorRow, fnRatio)))}
            sub={`at threshold ${cursorT.toFixed(2)} · FP·1 + FN·${fnRatio}`}
          />
          <KpiTile
            label="saves vs 0.5"
            value={
              Math.round(saved) === 0
                ? "even with 0.5"
                : `${saved < 0 ? "saves" : "costs"} ${Math.abs(Math.round(saved))}`
            }
            sub={`paired bootstrap CI${delta_ci.significant_95 ? " · 95% significant" : " · not significant"}`}
            tone={saved < 0 ? "good" : Math.round(saved) === 0 ? "neutral" : "bad"}
          />
          <KpiTile
            label="contacts"
            value={String(contactCount(cursorRow))}
            sub={`of ${payload.holdout_n} holdout customers`}
          />
          <KpiTile
            label="recall at t"
            value={`${Math.round(recallAt(cursorRow) * 100)}%`}
            sub={`of ${cursorRow.tp + cursorRow.fn} churners caught`}
          />
        </>
      }
      notice={
        <>
          <Notice>{noticeText(cursorRow, laxerRow, fnRatio)}</Notice>
          <Notice>{optimalityText(payload.overall, cursorIdx, fnRatio)}</Notice>
        </>
      }
      secondary={
        <>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">decision outcomes</h3>
            <OutcomesPanel row={cursorRow} holdoutN={payload.holdout_n} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">alarm burden by contract</h3>
            <SlicesPanel slices={payload.slices.contract} cursorT={cursorT} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">cost composition</h3>
            <CostCompositionPanel
              overall={payload.overall}
              thresholds={payload.thresholds}
              fnRatio={fnRatio}
              cursorIdx={cursorIdx}
            />
          </div>
        </>
      }
      evidence={
        <>
          <div className="wb-evidence-col">
            <h3 className="wb-evidence-tag">models used</h3>
            <p className="wb-evidence-line">
              {`${payload.model.name} — isotonic-calibrated champion (holdout n = ${payload.holdout_n}).`}
            </p>
            <p className="wb-evidence-line">
              {`Alarm rule: contact when predicted churn probability ≥ ${payload.model.threshold_selected} (pipeline-selected; default threshold ${payload.model.threshold_default}).`}
            </p>
            <p className="wb-evidence-line">
              {payload.cost_model.note.charAt(0).toUpperCase() + payload.cost_model.note.slice(1)}
            </p>
            {payload.report && (
              <p className="wb-evidence-line">
                <a href={payload.report}>Read the project report</a>
              </p>
            )}
          </div>
          <div className="wb-evidence-col">
            <h3 className="wb-evidence-tag">metrics results</h3>
            <p className="wb-evidence-line">
              {`Decision cost $${Math.round(payload.headline.cost_selected)} vs $${Math.round(payload.headline.cost_naive)} naive per ${payload.holdout_n} customers — paired bootstrap CI [${Math.round(payload.headline.delta_ci.lo)}, ${Math.round(payload.headline.delta_ci.hi)}]${payload.headline.delta_ci.significant_95 ? ", 95% significant" : ""}.`}
            </p>
            <p className="wb-evidence-line">
              {`roc-auc ${payload.model.roc_auc.toFixed(4)} · ece ${payload.model.ece.toFixed(4)} (lower is better)`}
            </p>
            <div className="wb-evidence-fig">
              <p className="wb-evidence-line">
                Calibration — static model-quality reference (isotonic-calibrated)
              </p>
              <div className="wb-evidence-calibration">
                <CalibrationScatter
                  points={payload.calibration.map((b) => ({
                    x: b.mean_predicted,
                    y: b.observed,
                    n: b.n,
                  }))}
                  height={180}
                />
              </div>
            </div>
          </div>
        </>
      }
      about={
        <>
          <p>
            <strong>What this shows.</strong> The campaign cost curve trades false alarms against
            missed churners as the alarm threshold moves — the cheapest cutoff shifts with the
            missed-churner cost, which is what the slider changes.
          </p>
          <p>
            <strong>The experiment.</strong> A calibrated classifier on the IBM Telco churn
            holdout; the target is to minimize decision cost FP·1 + FN·
            {payload.cost_model.fn_cost} per {payload.holdout_n} holdout customers.
          </p>
          <p>
            <strong>Key outcome.</strong> ${Math.round(payload.headline.cost_selected)} vs $
            {Math.round(payload.headline.cost_naive)} naive per {payload.holdout_n} customers —
            paired bootstrap CI [{Math.round(payload.headline.delta_ci.lo)},{" "}
            {Math.round(payload.headline.delta_ci.hi)}]
            {payload.headline.delta_ci.significant_95 ? ", 95% significant" : ""}.
          </p>
        </>
      }
    />
  );
}
