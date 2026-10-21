import { useEffect, useState, type ReactNode } from "react";
import { ApiError, scoreChurn } from "../../api";
import { CalibrationScatter } from "../charts/CalibrationScatter";
import { LineChart } from "../charts/LineChart";
import { MiniBars } from "../charts/MiniBars";
import { SegmentLegend, StackedHBar, type HBarSegment } from "../charts/StackedHBar";
import type { ChurnPayload, ConfusionRow, DemoManifest } from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import { contactCount, costAt, nearestIndex, noticeText, recallAt, savings } from "./kpis";
import { fetchChurnPayload, fetchManifest } from "./payload";

const C_TEAL = "#2dd4bf";
const C_PINK = "#f472b6";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";

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
function Figure({
  id,
  comment,
  children,
}: {
  id: string;
  comment: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="figure-card">
      <div className="demo-chart">{children}</div>
      <footer className="figure-card-band">
        <span className="figure-id">fig :: churn-sandbox/{id}</span>
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
  onCursor,
}: {
  payload: ChurnPayload;
  fnRatio: number;
  cursorIdx: number;
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

  return (
    <Figure
      id="cost-curve"
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
        markers={[
          { xIndex: defaultIdx, label: "default 0.5", style: "dashed" },
          { xIndex: selectedIdx, style: "star" },
        ]}
        ariaLabel="campaign cost over alarm threshold"
      />
      <p className="demo-hint">drag the chart to move the threshold</p>
    </Figure>
  );
}

// --- decision outcomes panel ------------------------------------------------------

function OutcomesPanel({ row, holdoutN }: { row: ConfusionRow; holdoutN: number }) {
  const perK = (v: number) => Math.round((v * 1000) / holdoutN);
  const segments: HBarSegment[] = [
    { label: "TP", value: perK(row.tp), color: C_TEAL },
    { label: "FP", value: perK(row.fp), color: C_AMBER },
    { label: "FN", value: perK(row.fn), color: C_PINK },
    { label: "TN", value: perK(row.tn), color: C_GRAY },
  ];
  return (
    <Figure
      id="outcomes"
      comment={
        <>
          The pink slice is churners the campaign misses at the cursor; every amber contact
          is a customer who would have stayed anyway.
        </>
      }
    >
      <StackedHBar segments={segments} ariaLabel="outcome mix at the cursor threshold" />
      <SegmentLegend segments={segments} />
      <p className="demo-hint">
        confusion-matrix counts at t = {row.t.toFixed(2)}, normalized per 1,000 customers
      </p>
    </Figure>
  );
}

// --- contract slices panel ----------------------------------------------------------

function SlicesPanel({ slices, cursorT }: { slices: Record<string, ConfusionRow[]>; cursorT: number }) {
  const rows = Object.entries(slices).map(([label, rowsForSlice]) => {
    const row = rowsForSlice[nearestIndex(rowsForSlice.map((r) => r.t), cursorT)];
    return { label, value: row.tp + row.fp, unit: "alarms" };
  });
  return (
    <Figure
      id="contract-slices"
      comment={
        <>
          Alarm burden by contract at the cursor — most of it lands on month-to-month
          customers, who churn the most and dominate the contact list.
        </>
      }
    >
      <MiniBars rows={rows} ariaLabel="alarm burden by contract" />
    </Figure>
  );
}

// --- calibration panel ---------------------------------------------------------------

function CalibrationPanel({ payload }: { payload: ChurnPayload }) {
  const { calibration, model } = payload;
  return (
    <Figure
      id="calibration"
      comment={
        <>
          Bins of predicted probability track the diagonal — the model is calibrated,
          with ECE = {model.ece.toFixed(4)} on the holdout.
        </>
      }
    >
      <CalibrationScatter
        points={calibration.map((b) => ({ x: b.mean_predicted, y: b.observed, n: b.n }))}
      />
    </Figure>
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
  payload: ChurnPayload;
  cursorT: number;
  form: Record<string, number | string>;
  setForm: (f: Record<string, number | string>) => void;
}) {
  const d = payload.feature_domains;
  const [score, setScore] = useState<ScoreState>({ status: "idle" });

  const set = (key: string, value: number | string) => setForm({ ...form, [key]: value });

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
    <Figure
      id="scorer"
      comment={
        <>
          The form drives the same serving artifact the experiment reports on; the alarm
          verdict uses the threshold under the cursor, not the committed one.
        </>
      }
    >
      <div className="demo-scorer">
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
            <select value={String(form.contract)} onChange={(e) => set("contract", e.target.value)}>
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
            <p className="demo-prob-line">churn probability {(score.probability * 100).toFixed(1)}%</p>
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
          <p className="state-box error demo-score-note">scoring request failed — try again</p>
        )}
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

  const cursorIdx = nearestIndex(payload.thresholds, controls.threshold);
  const cursorT = payload.thresholds[cursorIdx];
  const cursorRow = payload.overall[cursorIdx];
  const defaultRow = payload.overall[nearestIndex(payload.thresholds, payload.model.threshold_default)];
  const laxerRow = cursorIdx > 0 ? payload.overall[cursorIdx - 1] : null;
  const { delta_ci } = payload.headline;

  const moveCursor = (idx: number) => setControl("threshold", payload.thresholds[idx]);

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="demo-control">
            <label htmlFor="fn-ratio">a missed churner costs {fnRatio}× a false alarm</label>
            <input
              id="fn-ratio"
              type="range"
              min={1}
              max={10}
              step={1}
              value={fnRatio}
              onChange={(e) => setControl("fn_ratio", Number(e.target.value))}
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
        </>
      }
      canvas={<CostCurvePanel payload={payload} fnRatio={fnRatio} cursorIdx={cursorIdx} onCursor={moveCursor} />}
      kpis={
        <>
          <KpiTile
            label="cost at t"
            value={String(Math.round(costAt(cursorRow, fnRatio)))}
            sub={`at t = ${cursorT.toFixed(2)}`}
          />
          <KpiTile
            label="vs 0.5 default"
            value={`${savings(cursorRow, defaultRow, fnRatio) < 0 ? "saves" : "costs"} ${Math.abs(Math.round(savings(cursorRow, defaultRow, fnRatio)))}`}
            sub={delta_ci.significant_95 ? "95% significant" : "not significant"}
            tone={savings(cursorRow, defaultRow, fnRatio) < 0 ? "good" : "bad"}
          />
          <KpiTile
            label="contacts"
            value={`${contactCount(cursorRow)} of ${payload.holdout_n}`}
            sub="holdout customers contacted"
          />
          <KpiTile
            label="recall at t"
            value={`${Math.round(recallAt(cursorRow) * 100)}%`}
            sub={`of ${cursorRow.tp + cursorRow.fn} churners caught`}
          />
          <Notice>{noticeText(cursorRow, laxerRow, fnRatio)}</Notice>
        </>
      }
      details={
        <>
          <div className="wb-detail-panel">
            <h3 className="wb-rail-title">decision outcomes</h3>
            <OutcomesPanel row={cursorRow} holdoutN={payload.holdout_n} />
          </div>
          <div className="wb-detail-panel">
            <h3 className="wb-rail-title">alarm burden by contract</h3>
            <SlicesPanel slices={payload.slices.contract} cursorT={cursorT} />
          </div>
          <div className="wb-detail-panel">
            <h3 className="wb-rail-title">probability calibration</h3>
            <CalibrationPanel payload={payload} />
          </div>
          <div className="wb-detail-panel">
            <h3 className="wb-rail-title">score a customer</h3>
            {form !== null && (
              <ScorerCard key={presetKey} payload={payload} cursorT={cursorT} form={form} setForm={setForm} />
            )}
          </div>
        </>
      }
      evidence={
        <div className="wb-evidence-notes demo-footer">
          <p className="wb-evidence-line demo-footer-line">
            {`model: ${payload.model.name} · holdout n = ${payload.holdout_n} · roc-auc ${payload.model.roc_auc.toFixed(4)} · ece ${payload.model.ece.toFixed(4)}`}
          </p>
          <p className="wb-evidence-line">
            {`committed bootstrap CI on cost savings: ${Math.round(delta_ci.point)} [${Math.round(delta_ci.lo)}, ${Math.round(delta_ci.hi)}] per ${payload.holdout_n} customers (95% significant: ${delta_ci.significant_95 ? "yes" : "no"})`}
          </p>
          <p className="wb-evidence-line">{payload.cost_model.note}</p>
        </div>
      }
    />
  );
}
