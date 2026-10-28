import type { ReactNode } from "react";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { CatalogEntry, ForecastWorkbenchPayload, ForecastWindow } from "../types";
import { C_GRAY, MODELS } from "./chartData";
import { bandCalibration, wapeAt, weeklyAbsError } from "./kpis";

const NAIVE = "seasonal_naive";
const MODEL_COLORS = Object.fromEntries(MODELS.map((m) => [m.key, m.color]));
const MODEL_LABELS = Object.fromEntries(MODELS.map((m) => [m.key, m.label]));

/** Card with the shared figure-card chrome (viz region + commentary band). */
function Card({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

/**
 * Error composition: |error| by week for the primary model (solid, its model
 * color) against the seasonal-naive floor (wide grey underlay) over the
 * scored window, with the headline WAPE@h and the worst-week share. Mirrors
 * the churn demo's cost-composition panel; the footer is computed from the
 * weekly buckets, never canned.
 */
export function ErrorCompositionPanel({
  window,
  primary,
  h,
}: {
  window: ForecastWindow;
  /** Best active candidate (the KPI headline model); null → naive only. */
  primary: string | null;
  h: number;
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 110;
  const pad = { l: 34, r: 6, t: 6, b: 16 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;

  const modelKey = primary ?? NAIVE;
  const modelErr = weeklyAbsError(window.actual, window.curves[modelKey] ?? [], h);
  const naiveErr = weeklyAbsError(window.actual, window.curves[NAIVE] ?? [], h);
  const weeks = Math.max(modelErr.length, naiveErr.length, 1);
  const yMax = Math.max(...modelErr, ...naiveErr, 1) * 1.05;
  const slot = plotW / weeks;
  const barW = Math.min(slot * 0.3, 18);

  const modelWape = wapeAt(window.actual, window.curves[modelKey] ?? [], h);
  const naiveWape = wapeAt(window.actual, window.curves[NAIVE] ?? [], h);
  const deltaPts = (modelWape - naiveWape) * 100;

  const totalErr = modelErr.reduce((s, v) => s + v, 0);
  const worstIdx = modelErr.reduce((best, v, i) => (v > modelErr[best] ? i : best), 0);
  const worstShare = totalErr > 0 ? modelErr[worstIdx] / totalErr : 0;
  // self-comparison (naive is the only active candidate) gets an honest note
  // instead of a degenerate "vs itself" verdict.
  const selfOnly = modelKey === NAIVE;
  const naiveWorseThere = (naiveErr[worstIdx] ?? 0) > (modelErr[worstIdx] ?? 0);
  const modelTotalsLess = totalErr <= naiveErr.reduce((s, v) => s + v, 0);

  const yTicks = [0, yMax / 2, yMax];
  const py = (v: number) => pad.t + plotH - (v / yMax) * plotH;
  const base = pad.t + plotH;

  return (
    <Card
      comment={
        selfOnly ? (
          <>
            Only the seasonal naive is active — toggle a candidate on to decompose its weekly
            error against this floor.
          </>
        ) : (
          <>
            {MODEL_LABELS[modelKey]} concentrates {Math.round(worstShare * 100)}% of its window
            error in week {worstIdx + 1}
            {naiveWorseThere ? ", where the naive is off by even more" : ", though the naive tracks that week better"}
            {" "}— over the full window it totals {modelTotalsLess ? "less" : "more"} absolute error
            than the seasonal naive.
          </>
        )
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">
          wape @{h}d {modelWape.toFixed(3)}
        </span>
        <span
          className={`chip demo-readout ${selfOnly ? "" : deltaPts < 0 ? "good" : "bad"}`}
        >
          {selfOnly
            ? "floor"
            : `${deltaPts < 0 ? "−" : "+"}${Math.abs(deltaPts).toFixed(1)} pts vs naive`}
        </span>
      </div>
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="absolute error by week, primary model versus seasonal naive"
        >
          {yTicks.map((v) => (
            <g key={`y-${v}`}>
              <line
                x1={pad.l}
                y1={py(v)}
                x2={W - pad.r}
                y2={py(v)}
                stroke="var(--border)"
                strokeOpacity={v === 0 ? 1 : 0.4}
              />
              <text x={pad.l - 5} y={py(v) + 3} textAnchor="end" className="demo-axis-label">
                {Math.round(v)}
              </text>
            </g>
          ))}
          {Array.from({ length: weeks }, (_, i) => {
            const cx = pad.l + slot * i + slot / 2;
            return (
              <g key={`w-${i}`}>
                <rect
                  x={cx - barW / 2 - 1}
                  y={py(naiveErr[i] ?? 0)}
                  width={barW + 2}
                  height={Math.max(base - py(naiveErr[i] ?? 0), 0)}
                  fill={C_GRAY}
                  opacity={0.3}
                >
                  <title>{`week ${i + 1} naive: ${(naiveErr[i] ?? 0).toFixed(1)}`}</title>
                </rect>
                <rect
                  x={cx - barW / 2}
                  y={py(modelErr[i] ?? 0)}
                  width={barW}
                  height={Math.max(base - py(modelErr[i] ?? 0), 0)}
                  fill={MODEL_COLORS[modelKey] ?? C_GRAY}
                  opacity={0.85}
                >
                  <title>{`week ${i + 1} ${MODEL_LABELS[modelKey]}: ${(modelErr[i] ?? 0).toFixed(1)}`}</title>
                </rect>
                <text x={cx} y={H - 4} textAnchor="middle" className="demo-axis-label">
                  w{i + 1}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
}

/**
 * Band calibration: the coverage-so-far view of the LightGBM split-conformal
 * band at this origin — one square per scored day (teal = actual inside
 * p10/p90, pink = outside), the hit count and the mean band width, all
 * computed from the payload arrays for the selected series and horizon.
 * Collapses to a placeholder when LightGBM is deselected (the churn demo's
 * disabled-state pattern).
 */
export function BandCalibrationPanel({ window, h }: { window: ForecastWindow; h: number }) {
  const cal = bandCalibration(window, h);
  return (
    <Card
      comment={
        <>
          At this origin the committed 80% band catches {cal.hits} of {cal.n} scored days so far
          {" "}
          {cal.coverage >= 0.8 ? "at or above" : "just under"} its nominal level, averaging{" "}
          {cal.meanWidth.toFixed(1)} units wide.
        </>
      }
    >
      <div className="demo-readouts">
        <span className={`chip demo-readout ${cal.coverage >= 0.75 ? "good" : "bad"}`}>
          {cal.hits}/{cal.n} days inside
        </span>
        <span className="chip demo-readout">mean width {cal.meanWidth.toFixed(1)}u</span>
      </div>
      <div className="fwb-band-strip" role="img" aria-label="per-day band hit indicator">
        {Array.from({ length: cal.n }, (_, i) => {
          const hit = window.actual[i] >= window.band.p10[i] && window.actual[i] <= window.band.p90[i];
          return (
            <span
              key={i}
              className={`fwb-band-day ${hit ? "hit" : "miss"}`}
              title={`day +${i + 1}: ${hit ? "inside" : "outside"} [${window.band.p10[i].toFixed(1)}, ${window.band.p90[i].toFixed(
                1,
              )}] vs actual ${window.actual[i].toFixed(1)}`}
            />
          );
        })}
      </div>
    </Card>
  );
}

/** Compact disabled-state placeholder for the band card when lgbm is off. */
export function BandPlaceholder() {
  return (
    <Card comment={<>The conformal band belongs to the LightGBM candidate — switch it on to audit its coverage here.</>}>
      <p className="state-box fwb-band-off">enable LightGBM to see its band</p>
    </Card>
  );
}

/**
 * Model verdict: one mini-row per active candidate — name, window WAPE@h,
 * delta vs the seasonal-naive floor — with the best model highlighted. The
 * footer names the honest per-series outcome, including the intermittent
 * case where the naive can win a single window.
 */
export function VerdictPanel({
  entry,
  window,
  modelsOn,
  h,
  payload,
}: {
  entry: CatalogEntry;
  window: ForecastWindow;
  modelsOn: string[];
  h: number;
  payload: ForecastWorkbenchPayload;
}) {
  const rows = modelsOn
    .filter((m) => window.curves[m])
    .map((m) => ({ key: m, wape: wapeAt(window.actual, window.curves[m], h) }))
    .sort((a, b) => a.wape - b.wape);
  const naiveWape = wapeAt(window.actual, window.curves[NAIVE], h);
  const bestKey = rows[0]?.key ?? null;
  const naiveWins = bestKey === NAIVE;
  const pooled = payload.groups.test_pooled;
  const committedChip =
    h === 28 && bestKey && bestKey !== NAIVE && pooled[bestKey] && pooled[NAIVE]
      ? pooled[bestKey].wape - pooled[NAIVE].wape
      : null;
  const intermWinRate =
    payload.groups.win_rate_vs_naive.convex_ensemble?.intermittent ?? null;

  let comment: ReactNode;
  if (entry.class === "intermittent") {
    comment = naiveWins ? (
      <>
        This is an intermittent series — the seasonal naive wins this window on per-series WAPE,
        a real per-series loss
        {intermWinRate !== null &&
          ` even though the ensemble wins ${(intermWinRate * 100).toFixed(1)}% of intermittent series`}
        .
      </>
    ) : (
      <>
        Even on this intermittent series the {MODEL_LABELS[bestKey ?? NAIVE]} edges the naive on
        per-series WAPE here — the pooled committed gap is what generalises.
      </>
    );
  } else {
    comment = (
      <>
        On this dense series the {MODEL_LABELS[bestKey ?? NAIVE]} posts the lowest window WAPE at
        h = {h}; the committed pooled chip, not any single window, is the number that generalises.
      </>
    );
  }

  return (
    <Card comment={comment}>
      <div className="fwb-verdict">
        {rows.map((r) => {
          const delta = (r.wape - naiveWape) * 100;
          const isNaiveRow = r.key === NAIVE;
          return (
            <div
              key={r.key}
              className={`fwb-verdict-row ${r.key === bestKey ? "best" : ""}`}
            >
              <span className="fwb-verdict-name">
                <span className="fwb-dot" style={{ background: MODEL_COLORS[r.key] }} />
                {MODEL_LABELS[r.key]}
                {r.key === bestKey && <span className="fwb-verdict-crown">best</span>}
              </span>
              <span className="fwb-verdict-wape">{r.wape.toFixed(3)}</span>
              <span className={`chip demo-readout ${isNaiveRow ? "" : delta < 0 ? "good" : "bad"}`}>
                {isNaiveRow ? "floor" : `${delta < 0 ? "−" : "+"}${Math.abs(delta).toFixed(1)} pts`}
              </span>
            </div>
          );
        })}
        {committedChip !== null && (
          <p className="fwb-verdict-committed">
            pooled {committedChip > 0 ? "+" : "−"}
            {Math.abs(committedChip * 100).toFixed(1)} pts committed
          </p>
        )}
      </div>
    </Card>
  );
}
