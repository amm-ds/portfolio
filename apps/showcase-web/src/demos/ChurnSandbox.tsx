import { useEffect, useMemo, useRef, useState } from "react";
import { getDemoPayload, scoreChurn, ApiError } from "../api";
import { DemoShell } from "./DemoShell";

// --- payload contract (GET /demos/churn-sandbox/payload) ----------------------

export interface ConfusionRow {
  t: number;
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface CalibrationBin {
  bin_lo: number;
  bin_hi: number;
  n: number;
  mean_predicted: number;
  observed: number;
}

export interface CustomerPreset {
  label: string;
  features: {
    tenure_months: number;
    monthly_charges: number;
    contract: string;
    internet_service: string;
  };
  churn_probability: number;
}

export interface ChurnSandboxPayload {
  demo: string;
  project: string;
  holdout_n: number;
  model: {
    name: string;
    roc_auc: number;
    ece: number;
    threshold_default: number;
    threshold_selected: number;
  };
  cost_model: { fp_cost: number; fn_cost: number; note: string };
  headline: {
    cost_naive: number;
    cost_selected: number;
    delta_ci: { point: number; lo: number; hi: number; significant_95: boolean };
  };
  thresholds: number[];
  overall: ConfusionRow[];
  slices: Record<string, Record<string, ConfusionRow[]>>;
  calibration: CalibrationBin[];
  customers: CustomerPreset[];
  feature_domains: {
    tenure_months: { min: number; max: number };
    monthly_charges: { min: number; max: number };
    contract: string[];
    internet_service: string[];
  };
  roc_auc: number;
}

// --- client-side cost math ------------------------------------------------------

/** cost(t) = fp_cost·FP + fn_cost·FN with fp_cost = 1 (per the payload cost model). */
function rowCost(row: ConfusionRow, fnRatio: number): number {
  return row.fp + fnRatio * row.fn;
}

function nearestIdx(thresholds: number[], t: number): number {
  let best = 0;
  for (let i = 1; i < thresholds.length; i++) {
    if (Math.abs(thresholds[i] - t) < Math.abs(thresholds[best] - t)) best = i;
  }
  return best;
}

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

// --- cost curve panel ------------------------------------------------------------

const VW = 720;
const VH = 280;
const PAD = { l: 52, r: 18, t: 16, b: 32 };

function CostCurvePanel({
  payload,
  fnRatio,
  cursorIdx,
  onCursor,
}: {
  payload: ChurnSandboxPayload;
  fnRatio: number;
  cursorIdx: number;
  onCursor: (idx: number) => void;
}) {
  const { thresholds, overall, model } = payload;
  const costs = useMemo(() => overall.map((r) => rowCost(r, fnRatio)), [overall, fnRatio]);
  const defaultIdx = nearestIdx(thresholds, model.threshold_default);
  const selectedIdx = nearestIdx(thresholds, model.threshold_selected);

  const tMin = thresholds[0];
  const tMax = thresholds[thresholds.length - 1];
  const cMax = Math.max(...costs, 1) * 1.08;
  const plotW = VW - PAD.l - PAD.r;
  const plotH = VH - PAD.t - PAD.b;
  const x = (t: number) => PAD.l + ((t - tMin) / (tMax - tMin)) * plotW;
  const y = (c: number) => PAD.t + plotH - (c / cMax) * plotH;

  const points = thresholds.map((t, i) => `${x(t).toFixed(1)},${y(costs[i]).toFixed(1)}`);
  const cursorT = thresholds[cursorIdx];
  const cursorCost = costs[cursorIdx];
  const defaultCost = costs[defaultIdx];
  const savings = cursorCost - defaultCost;
  const cursorRow = overall[cursorIdx];

  // pointer position → nearest grid threshold (viewBox-aware for CSS scaling)
  const svgRef = useRef<SVGSVGElement | null>(null);
  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * VW;
    const frac = (vx - PAD.l) / plotW;
    const t = tMin + Math.min(1, Math.max(0, frac)) * (tMax - tMin);
    onCursor(nearestIdx(thresholds, t));
  };

  const xTicks = [tMin, (tMin + tMax) / 2, tMax];

  return (
    <div className="figure-card">
      <div className="demo-chart">
        <div className="demo-readouts">
          <span className="chip demo-readout">threshold t = {cursorT.toFixed(2)}</span>
          <span className="chip demo-readout">cost at t: {Math.round(cursorCost)}</span>
          <span className="chip demo-readout">cost at 0.5: {Math.round(defaultCost)}</span>
          <span className={`chip demo-readout ${savings < 0 ? "good" : "bad"}`}>
            {savings < 0 ? "saves" : "costs"} {Math.abs(Math.round(savings))} vs 0.5
          </span>
          <span className="chip demo-readout">
            contact {cursorRow.fp + cursorRow.tp} of {payload.holdout_n}
          </span>
        </div>
        <svg
          ref={svgRef}
          className="cost-curve-svg"
          viewBox={`0 0 ${VW} ${VH}`}
          role="img"
          aria-label="campaign cost over alarm threshold"
          onPointerDown={(e) => {
            pick(e.clientX);
            if (e.pointerId !== undefined) {
              try {
                e.currentTarget.setPointerCapture?.(e.pointerId);
              } catch {
                // jsdom / older browsers: drag still works via pointermove buttons
              }
            }
          }}
          onPointerMove={(e) => {
            if (e.buttons > 0) pick(e.clientX);
          }}
        >
          {/* axes */}
          <line x1={PAD.l} y1={VH - PAD.b} x2={VW - PAD.r} y2={VH - PAD.b} stroke="var(--border)" />
          <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={VH - PAD.b} stroke="var(--border)" />
          {xTicks.map((t) => (
            <g key={t}>
              <line x1={x(t)} y1={VH - PAD.b} x2={x(t)} y2={VH - PAD.b + 4} stroke="var(--border)" />
              <text x={x(t)} y={VH - PAD.b + 16} textAnchor="middle" className="demo-axis-label">
                {t.toFixed(2)}
              </text>
            </g>
          ))}
          <text x={PAD.l - 8} y={PAD.t + 6} textAnchor="end" className="demo-axis-label">
            {Math.round(cMax)}
          </text>
          <text x={PAD.l - 8} y={VH - PAD.b} textAnchor="end" className="demo-axis-label">
            0
          </text>
          {/* default threshold marker */}
          <line
            x1={x(thresholds[defaultIdx])}
            y1={PAD.t}
            x2={x(thresholds[defaultIdx])}
            y2={VH - PAD.b}
            stroke="var(--muted)"
            strokeDasharray="4 4"
          />
          <text
            x={x(thresholds[defaultIdx]) + 4}
            y={PAD.t + 10}
            className="demo-axis-label"
          >
            default 0.5
          </text>
          {/* committed (cost-selected) threshold star */}
          <text
            x={x(thresholds[selectedIdx])}
            y={y(costs[selectedIdx]) - 10}
            textAnchor="middle"
            className="demo-star"
          >
            ★
          </text>
          {/* cost curve */}
          <polyline points={points.join(" ")} fill="none" stroke={C_TEAL} strokeWidth={2} />
          {/* draggable cursor */}
          <line
            x1={x(cursorT)}
            y1={PAD.t}
            x2={x(cursorT)}
            y2={VH - PAD.b}
            stroke={C_PINK}
            strokeWidth={1.5}
          />
          <circle cx={x(cursorT)} cy={y(cursorCost)} r={5} fill={C_PINK} />
        </svg>
        <p className="demo-hint">drag the chart to move the threshold</p>
      </div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/cost-curve</span>
        <p className="figure-comment">
          Cost = FP + N×FN on the untouched holdout; drag the cursor and the curve refits
          when the multiplier changes — the star marks the threshold the pipeline committed to.
        </p>
      </footer>
    </div>
  );
}

// --- decision outcomes panel ------------------------------------------------------

function OutcomesPanel({
  row,
  holdoutN,
}: {
  row: ConfusionRow;
  holdoutN: number;
}) {
  const perK = (v: number) => Math.round((v * 1000) / holdoutN);
  const segments = [
    { key: "TP", value: perK(row.tp), color: C_TEAL },
    { key: "FP", value: perK(row.fp), color: C_AMBER },
    { key: "FN", value: perK(row.fn), color: C_PINK },
    { key: "TN", value: perK(row.tn), color: C_GRAY },
  ];
  return (
    <div className="figure-card">
      <div className="demo-chart">
        <div className="demo-stack-bar" role="img" aria-label="outcome mix at the cursor threshold">
          {segments.map((s) =>
            s.value > 0 ? (
              <span
                key={s.key}
                style={{ width: `${(s.value / 1000) * 100}%`, background: s.color }}
                title={`${s.key}: ${s.value}`}
              />
            ) : null,
          )}
        </div>
        <ul className="demo-outcome-legend">
          {segments.map((s) => (
            <li key={s.key}>
              <span className="demo-swatch" style={{ background: s.color }} />
              <span className="demo-outcome-count">
                {s.key} {s.value}
              </span>
            </li>
          ))}
        </ul>
        <p className="demo-hint">
          confusion-matrix counts at t = {row.t.toFixed(2)}, normalized per 1,000 customers
        </p>
      </div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/outcomes</span>
        <p className="figure-comment">
          The pink slice is churners the campaign misses at the cursor; every amber contact
          is a customer who would have stayed anyway.
        </p>
      </footer>
    </div>
  );
}

// --- contract slices panel ----------------------------------------------------------

function SlicesPanel({
  slices,
  cursorT,
}: {
  slices: Record<string, ConfusionRow[]>;
  cursorT: number;
}) {
  const entries = Object.entries(slices).map(([label, rows]) => {
    const row = rows[nearestIdx(rows.map((r) => r.t), cursorT)];
    return { label, alarms: row.tp + row.fp, row };
  });
  const maxAlarms = Math.max(...entries.map((e) => e.alarms), 1);
  return (
    <div className="figure-card">
      <div className="demo-chart">
        <ul className="demo-slice-list">
          {entries.map((e) => (
            <li key={e.label}>
              <span className="demo-slice-label">{e.label}</span>
              <span className="demo-slice-bar">
                <span style={{ width: `${(e.alarms / maxAlarms) * 100}%` }} />
              </span>
              <span className="demo-slice-count">{e.alarms} alarms</span>
            </li>
          ))}
        </ul>
      </div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/contract-slices</span>
        <p className="figure-comment">
          Alarm burden by contract at the cursor — most of it lands on month-to-month
          customers, who churn the most and dominate the contact list.
        </p>
      </footer>
    </div>
  );
}

// --- calibration panel ---------------------------------------------------------------

function CalibrationPanel({
  calibration,
  ece,
}: {
  calibration: CalibrationBin[];
  ece: number;
}) {
  const CW = 340;
  const CH = 260;
  const CP = { l: 40, r: 14, t: 14, b: 34 };
  const plotW = CW - CP.l - CP.r;
  const plotH = CH - CP.t - CP.b;
  const cx = (v: number) => CP.l + v * plotW;
  const cy = (v: number) => CP.t + plotH - v * plotH;
  const maxN = Math.max(...calibration.map((b) => b.n), 1);
  return (
    <div className="figure-card">
      <div className="demo-chart">
        <svg viewBox={`0 0 ${CW} ${CH}`} role="img" aria-label="calibration scatter">
          <line x1={cx(0)} y1={cy(0)} x2={cx(1)} y2={cy(0)} stroke="var(--border)" />
          <line x1={cx(0)} y1={cy(0)} x2={cx(0)} y2={cy(1)} stroke="var(--border)" />
          <line
            x1={cx(0)}
            y1={cy(0)}
            x2={cx(1)}
            y2={cy(1)}
            stroke="var(--muted)"
            strokeDasharray="4 4"
          />
          <text x={cx(1)} y={cy(0) + 16} textAnchor="end" className="demo-axis-label">
            predicted
          </text>
          <text x={cx(0) + 4} y={cy(1) + 12} className="demo-axis-label">
            observed
          </text>
          {calibration.map((b) => (
            <circle
              key={b.bin_lo}
              cx={cx(b.mean_predicted)}
              cy={cy(b.observed)}
              r={3 + 9 * Math.sqrt(b.n / maxN)}
              fill={C_TEAL}
              fillOpacity={0.75}
            >
              <title>
                p̂ {b.mean_predicted.toFixed(2)} → {b.observed.toFixed(2)} (n = {b.n})
              </title>
            </circle>
          ))}
        </svg>
      </div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/calibration</span>
        <p className="figure-comment">
          Bins of predicted probability track the diagonal — the model is calibrated,
          with ECE = {ece.toFixed(4)} on the holdout.
        </p>
      </footer>
    </div>
  );
}

// --- customer scorer card -------------------------------------------------------------

type ScoreState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; probability: number }
  | { status: "unavailable" }
  | { status: "error" };

function ScorerCard({
  payload,
  cursorT,
  form,
  setForm,
}: {
  payload: ChurnSandboxPayload;
  cursorT: number;
  form: Record<string, number | string>;
  setForm: (f: Record<string, number | string>) => void;
}) {
  const d = payload.feature_domains;
  const [score, setScore] = useState<ScoreState>({ status: "idle" });

  const set = (key: string, value: number | string) =>
    setForm({ ...form, [key]: value });

  const scoreLive = () => {
    setScore({ status: "loading" });
    scoreChurn(payload.project, form)
      .then((r) => setScore({ status: "ok", probability: r.churn_probability }))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 503) {
          setScore({ status: "unavailable" });
        } else {
          setScore({ status: "error" });
        }
      });
  };

  const alarm = score.status === "ok" && score.probability >= cursorT;
  const nearestPreset =
    score.status === "ok"
      ? payload.customers.reduce((best, c) =>
          Math.abs(c.churn_probability - score.probability) <
          Math.abs(best.churn_probability - score.probability)
            ? c
            : best,
        )
      : null;

  return (
    <div className="figure-card">
      <div className="demo-chart demo-scorer">
        <div className="demo-form">
          <label>
            tenure (months)
            <input
              type="number"
              min={d.tenure_months.min}
              max={d.tenure_months.max}
              value={Number(form.tenure_months)}
              onChange={(e) => set("tenure_months", Number(e.target.value))}
            />
          </label>
          <label>
            monthly charges
            <input
              type="number"
              min={d.monthly_charges.min}
              max={d.monthly_charges.max}
              value={Number(form.monthly_charges)}
              onChange={(e) => set("monthly_charges", Number(e.target.value))}
            />
          </label>
          <label>
            contract
            <select
              value={String(form.contract)}
              onChange={(e) => set("contract", e.target.value)}
            >
              {d.contract.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label>
            internet service
            <select
              value={String(form.internet_service)}
              onChange={(e) => set("internet_service", e.target.value)}
            >
              {d.internet_service.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={scoreLive} disabled={score.status === "loading"}>
            {score.status === "loading" ? "scoring…" : "score live"}
          </button>
        </div>
        {score.status === "ok" && (
          <div className="demo-score-result">
            <div className="demo-prob-bar">
              <span style={{ width: `${score.probability * 100}%` }} />
            </div>
            <p className="demo-prob-line">
              churn probability {(score.probability * 100).toFixed(1)}%
            </p>
            <p className={`demo-alarm ${alarm ? "alarm" : "calm"}`}>
              {alarm
                ? `alarm at t = ${cursorT.toFixed(2)} — this customer gets contacted`
                : `no alarm at t = ${cursorT.toFixed(2)} — below the cursor`}
            </p>
            {nearestPreset && (
              <p className="demo-hint">
                closest preset band: {nearestPreset.label} (p ={" "}
                {nearestPreset.churn_probability.toFixed(2)})
              </p>
            )}
          </div>
        )}
        {score.status === "unavailable" && (
          <p className="state-box demo-score-note">
            live scoring unavailable — showing precomputed presets only
          </p>
        )}
        {score.status === "error" && (
          <p className="state-box error demo-score-note">
            scoring request failed — try again
          </p>
        )}
      </div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/scorer</span>
        <p className="figure-comment">
          The form drives the same serving artifact the experiment reports on; the alarm
          verdict uses the threshold under the cursor, not the committed one.
        </p>
      </footer>
    </div>
  );
}

// --- demo ------------------------------------------------------------------------------

export function ChurnSandbox() {
  const [payload, setPayload] = useState<ChurnSandboxPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fnRatio, setFnRatio] = useState(5);
  const [cursorIdx, setCursorIdx] = useState(0);
  const [form, setForm] = useState<Record<string, number | string> | null>(null);
  const [presetKey, setPresetKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getDemoPayload<ChurnSandboxPayload>("churn-sandbox")
      .then((p) => {
        if (cancelled) return;
        setPayload(p);
        setFnRatio(p.cost_model.fn_cost);
        setCursorIdx(nearestIdx(p.thresholds, p.model.threshold_selected));
        setForm({ ...p.customers[0].features });
      })
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

  const cursorT = payload.thresholds[cursorIdx];
  const cursorRow = payload.overall[cursorIdx];
  const { delta_ci } = payload.headline;

  return (
    <DemoShell
      title="churn threshold sandbox"
      hook="Move the alarm threshold and the missed-churner cost — watch the optimal cutoff and the saved budget change on a real churn model."
      projectId={payload.project}
      footerLines={[
        `model: ${payload.model.name} · holdout n = ${payload.holdout_n} · roc-auc ${payload.model.roc_auc.toFixed(4)} · ece ${payload.model.ece.toFixed(4)}`,
        `committed bootstrap CI on cost savings: ${Math.round(delta_ci.point)} [${Math.round(delta_ci.lo)}, ${Math.round(delta_ci.hi)}] per ${payload.holdout_n} customers (95% significant: ${delta_ci.significant_95 ? "yes" : "no"})`,
        `${payload.cost_model.note}`,
      ]}
    >
      <div className="demo-controls">
        <div className="demo-control">
          <label htmlFor="fn-ratio">a missed churner costs {fnRatio}× a false alarm</label>
          <input
            id="fn-ratio"
            type="range"
            min={1}
            max={10}
            step={1}
            value={fnRatio}
            onChange={(e) => setFnRatio(Number(e.target.value))}
          />
        </div>
        <div className="demo-control">
          <span className="demo-control-label">preset customers (fill the scorer form)</span>
          <div className="demo-presets">
            {payload.customers.map((c) => (
              <button
                key={c.label}
                type="button"
                className="chip demo-preset"
                onClick={() => {
                  setForm({ ...c.features });
                  setPresetKey((k) => k + 1);
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <h2 className="section-title">cost curve</h2>
      <CostCurvePanel
        payload={payload}
        fnRatio={fnRatio}
        cursorIdx={cursorIdx}
        onCursor={setCursorIdx}
      />

      <div className="demo-two-col">
        <div>
          <h2 className="section-title">decision outcomes</h2>
          <OutcomesPanel row={cursorRow} holdoutN={payload.holdout_n} />
        </div>
        <div>
          <h2 className="section-title">alarm burden by contract</h2>
          <SlicesPanel slices={payload.slices.contract} cursorT={cursorT} />
        </div>
      </div>

      <h2 className="section-title">probability calibration</h2>
      <CalibrationPanel calibration={payload.calibration} ece={payload.model.ece} />

      <h2 className="section-title">score a customer</h2>
      {form !== null && (
        <ScorerCard
          key={presetKey}
          payload={payload}
          cursorT={cursorT}
          form={form}
          setForm={setForm}
        />
      )}
    </DemoShell>
  );
}
