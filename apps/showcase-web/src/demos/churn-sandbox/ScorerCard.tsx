import { useState } from "react";
import { ApiError, scoreChurn } from "../../api";
import type { ChurnPayload } from "../types";

type ScoreState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; probability: number }
  | { status: "unavailable" }
  | { status: "error" };

/**
 * Score-a-customer card: lives in the workbench controls column (churn
 * sandbox only — demo-specific pattern, not shared workbench chrome). The
 * form drives the live serving endpoint; `onScore` reports the returned
 * probability upstream so the demo can mark the customer on the cost curve.
 */
export function ScorerCard({
  payload,
  cursorT,
  form,
  setForm,
  onScore,
}: {
  payload: ChurnPayload;
  cursorT: number;
  form: Record<string, number | string>;
  setForm: (f: Record<string, number | string>) => void;
  onScore: (probability: number) => void;
}) {
  const d = payload.feature_domains;
  const [score, setScore] = useState<ScoreState>({ status: "idle" });

  const set = (key: string, value: number | string) => setForm({ ...form, [key]: value });

  const scoreLive = () => {
    setScore({ status: "loading" });
    scoreChurn(payload.project, form)
      .then((r) => {
        setScore({ status: "ok", probability: r.churn_probability });
        onScore(r.churn_probability);
      })
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
    <div className="demo-control wb-scorer">
      <form
        id="wb-scorer-form"
        className="demo-form"
        onSubmit={(e) => {
          e.preventDefault();
          scoreLive();
        }}
      >
        <div className="wb-scorer-head">
          <span className="wb-scorer-label">score a customer</span>
          <button type="submit" form="wb-scorer-form" disabled={score.status === "loading"}>
            {score.status === "loading" ? "scoring…" : "score live"}
          </button>
        </div>
        {score.status === "ok" && (
          <div className="demo-score-result">
            <div className="demo-prob-bar">
              <span style={{ width: `${score.probability * 100}%` }} />
            </div>
            <p className="demo-prob-line">Churn probability {(score.probability * 100).toFixed(1)}%</p>
            <p className={`demo-alarm ${alarm ? "alarm" : "calm"}`}>
              {alarm
                ? `Alarm at t = ${cursorT.toFixed(2)} — this customer gets contacted`
                : `No alarm at t = ${cursorT.toFixed(2)} — below the cursor`}
            </p>
            {nearestPreset && (
              <p className="demo-hint">
                Closest preset band: {nearestPreset.label} (p ={" "}
                {nearestPreset.churn_probability.toFixed(2)})
              </p>
            )}
          </div>
        )}
        <label>
          tenure (mo)
          <input
            type="number"
            min={d.tenure_months.min}
            max={d.tenure_months.max}
            value={Number(form.tenure_months)}
            onChange={(e) => set("tenure_months", Number(e.target.value))}
          />
        </label>
        <label>
          charges ($/mo)
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
          internet
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
      </form>
      {score.status === "unavailable" && (
        <p className="state-box demo-score-note">
          Live scoring unavailable — showing precomputed presets only
        </p>
      )}
      {score.status === "error" && (
        <p className="state-box error demo-score-note">Scoring request failed — try again</p>
      )}
    </div>
  );
}
