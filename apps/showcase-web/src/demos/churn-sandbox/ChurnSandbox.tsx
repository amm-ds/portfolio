import { useEffect, useState, type CSSProperties } from "react";
import { LineChart, type LineMarker } from "../charts/LineChart";
import { SegmentLegend, type HBarSegment } from "../charts/StackedHBar";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { ChurnPayload, ConfusionRow, DemoManifest } from "../types";
import { DemoFigure, DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import { contactCount, costAt, nearestIndex, recallAt, rowCost, savings } from "./kpis";
import { CostCompositionPanel } from "./CostCompositionPanel";
import { fetchChurnPayload, fetchManifest } from "./payload";
import { usePageMeta } from "../../seo";
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

/** Trade-off tile: dynamic values (multiplier, alarms per catch, recall) in bold. */
function TradeoffText({
  row,
  laxer,
  fnRatio,
}: {
  row: ConfusionRow;
  laxer: ConfusionRow | null;
  fnRatio: number;
}) {
  if (laxer && laxer.tp > row.tp) {
    const gained = laxer.tp - row.tp;
    const extraAlarms = Math.max(laxer.fp + laxer.tp - (row.fp + row.tp), 0);
    const per = extraAlarms / gained;
    const rounded = per >= 10 ? Math.round(per) : Math.round(per * 10) / 10;
    return (
      <>
        At <strong>{fnRatio}×</strong> a miss, catching one more churner here costs ~
        <strong>{rounded}</strong> extra false alarms
      </>
    );
  }
  const recall = Math.round((row.tp / Math.max(row.tp + row.fn, 1)) * 100);
  return (
    <>
      At <strong>{fnRatio}×</strong> a miss this threshold already catches{" "}
      <strong>{recall}%</strong> of churners — every additional alarm is a false one
    </>
    );
}

/** Optimality tile: names the cheapest cutoff and the gap, dynamics in bold. */
function OptimalityText({
  overall,
  cursorIdx,
  fnRatio,
}: {
  overall: ConfusionRow[];
  cursorIdx: number;
  fnRatio: number;
}) {
  const cursor = overall[cursorIdx];
  if (!cursor || overall.length === 0) {
    return <>Move the cursor to compare against the cheapest cutoff.</>;
  }
  let bestIdx = 0;
  for (let i = 1; i < overall.length; i++) {
    if (rowCost(overall[i], fnRatio) < rowCost(overall[bestIdx], fnRatio)) bestIdx = i;
  }
  if (bestIdx === cursorIdx) {
    return (
      <>
        This is the cheapest cutoff for a <strong>{fnRatio}×</strong> miss cost
      </>
    );
  }
  const optimal = overall[bestIdx];
  const direction = optimal.t > cursor.t ? "above" : "below";
  const gap = Math.abs(optimal.t - cursor.t).toFixed(2);
  return (
    <>
      The cheapest cutoff at <strong>{fnRatio}×</strong> is <strong>t = {optimal.t.toFixed(2)}</strong>{" "}
      — {direction} your cursor by <strong>{gap}</strong>
    </>
  );
}

/** Live score result: rendered in the full-width strip below the main row —
 * outside the scorer box, in the space reserved below it. */
function ScoreResultPanel({
  probability,
  cursorT,
  label,
}: {
  probability: number;
  cursorT: number;
  label: string;
}) {
  const alarm = probability >= cursorT;
  return (
    <div className="wb-score-result" data-testid="score-result">
      <span className="wb-evidence-tag">score result · {label}</span>
      <div className="demo-prob-bar">
        <span style={{ width: `${probability * 100}%` }} />
      </div>
      <p className="demo-prob-line">
        Churn probability <strong>{(probability * 100).toFixed(1)}%</strong>
      </p>
      <p className={`demo-alarm ${alarm ? "alarm" : "calm"}`}>
        {alarm
          ? `Alarm at t = ${cursorT.toFixed(2)} — this customer gets contacted`
          : `No alarm at t = ${cursorT.toFixed(2)} — below the cursor`}
      </p>
    </div>
  );
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
    { name: "base", controls: { fn_ratio: 5, threshold: 0.15 } },
    { name: "high-cost-miss", controls: { fn_ratio: 9, threshold: 0.12 } },
    { name: "default-threshold", controls: { fn_ratio: 5, threshold: 0.5 } },
  ],
  live_endpoints: [
    { method: "POST", path: "/projects/05-ml-pipeline-churn/score", label: "live customer scoring", cost: "free-local" },
  ],
  payload: {
    path: "reports/demo_payload.json",
    schema_version: 1,
    required_keys: ["demo", "project", "holdout_n", "model", "cost_model", "headline", "thresholds", "overall", "slices", "calibration", "customers", "feature_domains", "roc_auc"],
  },
};

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
      color: C_TEAL,
    });
  }

  return (
    <DemoFigure
      comment={
        <>
          Cost = FP + N×FN on the untouched holdout; drag the cursor and the curve recomputes
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
      <div className="demo-chart">
        <LineChart
          x={thresholds}
          series={[{ name: "cost", color: C_TEAL, values: costs }]}
          cursor={cursorIdx}
          onCursorChange={onCursor}
          markers={markers}
          ariaLabel="campaign cost over alarm threshold"
        />
      </div>
      <p className="demo-hint">drag the chart to move the threshold</p>
    </DemoFigure>
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
    <DemoFigure
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
    </DemoFigure>
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
  // scale against the busiest threshold seen per contract (static max): the
  // top segment is not pinned at 100% and every bar moves with the cursor
  const max = Math.max(
    ...Object.values(slices).flatMap((rs) => rs.map((r) => r.tp + r.fp)),
    1,
  );
  const pad = 14;
  const labelW = Math.min(120, W * 0.35);
  const countW = 92;
  const barX = pad + labelW + 8;
  // reserve generous right margin so the count ("675 alarms") never touches
  // the bar end
  const barW = Math.max(W - barX - countW - pad - 12, 0);
  const rowH = rows.length > 0 ? H / rows.length : H;
  return (
    <DemoFigure
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
                <text x={pad} y={cy + 3} className="demo-axis-label">
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
                <text x={W - pad} y={cy + 3} textAnchor="end" className="demo-axis-label">
                  {r.value} {r.unit}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </DemoFigure>
  );
}

// --- demo ------------------------------------------------------------------------------

export default function ChurnSandbox() {
  usePageMeta({
    title: "Churn threshold sandbox",
    description:
      "Interactive churn demo: move the alarm threshold and the missed-churner cost, watch the optimal cutoff and the saved budget respond.",
  });

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
  // selected customer: defaults to the first preset (marker + result visible
  // on load); preset chips and live scores change it
  const [customer, setCustomer] = useState<CustomerMarker | null>(() =>
    payload.customers.length > 0
      ? {
          label: shortLabel(payload.customers[0].label),
          probability: payload.customers[0].churn_probability,
        }
      : null,
  );
  const [score, setScore] = useState<number | null>(
    payload.customers.length > 0 ? payload.customers[0].churn_probability : null,
  );

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
                  aria-valuetext={`${fnRatio} times`}
                  style={{ "--fill": `${((fnRatio - 1) / 9) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("fn_ratio", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{fnRatio}×</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-threshold">
            <label className="wb-rail-title" htmlFor="alarm-threshold">
              Alarm threshold
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="alarm-threshold"
                  type="range"
                  className="wb-slider"
                  min={0}
                  max={payload.thresholds.length - 1}
                  step={1}
                  value={cursorIdx}
                  aria-valuetext={`t = ${cursorT.toFixed(2)}`}
                  style={{
                    "--fill": `${(cursorIdx / Math.max(payload.thresholds.length - 1, 1)) * 100}%`,
                  } as CSSProperties}
                  onChange={(e) => moveCursor(Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{cursorT.toFixed(2)}</span>
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
                      setScore(c.churn_probability);
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
                form={form}
                setForm={setForm}
                onScore={(probability) => {
                  setCustomer({ label: nearestPresetLabel(probability), probability });
                  setScore(probability);
                }}
              />
            </div>
          )}
          {score !== null && customer !== null && (
            <ScoreResultPanel probability={score} cursorT={cursorT} label={customer.label} />
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
          <Notice>
            <TradeoffText row={cursorRow} laxer={laxerRow} fnRatio={fnRatio} />
          </Notice>
          <Notice>
            <OptimalityText overall={payload.overall} cursorIdx={cursorIdx} fnRatio={fnRatio} />
          </Notice>
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
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              <code className="wb-tag">{payload.model.name}</code> — isotonic-calibrated
              champion, holdout n = {payload.holdout_n}.
            </p>
            <p className="wb-evidence-line">
              Alarm rule: contact when predicted churn probability ≥{" "}
              <strong>{payload.model.threshold_selected}</strong> (pipeline-selected; default{" "}
              {payload.model.threshold_default}).
            </p>
            <p className="wb-evidence-line">
              {payload.cost_model.note.charAt(0).toUpperCase() + payload.cost_model.note.slice(1)}
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">metrics results</h4>
            <p className="wb-evidence-line">
              Decision cost <strong>${Math.round(payload.headline.cost_selected)}</strong> vs{" "}
              <strong>${Math.round(payload.headline.cost_naive)}</strong> naive per{" "}
              {payload.holdout_n} customers — paired bootstrap CI [
              {Math.round(payload.headline.delta_ci.lo)}, {Math.round(payload.headline.delta_ci.hi)}
              ]{payload.headline.delta_ci.significant_95 ? ", 95% significant" : ""}.
            </p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">roc-auc {payload.model.roc_auc.toFixed(4)}</span>
              <span className="wb-tag">ece {payload.model.ece.toFixed(4)}</span>
              <span className="wb-tag">threshold {payload.model.threshold_selected}</span>
            </p>
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The campaign cost curve trades false alarms against missed churners as the alarm
              threshold moves — the cheapest cutoff shifts with the{" "}
              <strong>FP/FN cost ratio</strong>, which is what the slider changes.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              A calibrated classifier on the IBM Telco churn holdout; the target is to minimize
              decision cost <span className="wb-tag">FP·1 + FN·{payload.cost_model.fn_cost}</span>{" "}
              per {payload.holdout_n} holdout customers.
            </p>
          </div>
        </>
      }
    />
  );
}
