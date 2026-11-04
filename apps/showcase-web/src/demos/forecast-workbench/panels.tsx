import type { ReactNode } from "react";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { CatalogEntry, ForecastWorkbenchPayload, ForecastWindow } from "../types";
import { DemoFigure } from "../workbench";
import { C_GRAY, MODEL_COLORS, MODEL_LABELS } from "./chartData";
import { peakAbsError, wapeAt, weeklyAbsError } from "./kpis";

const NAIVE = "seasonal_naive";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Compact "May 24" rendering of a forecast date; falls back to the day slot. */
function shortDate(dates: string[], day: number): string {
  const d = dates[day];
  const parts = d ? d.split("-") : [];
  if (parts.length !== 3) return `day +${day + 1}`;
  return `${MONTHS[Number(parts[1]) - 1] ?? parts[1]} ${Number(parts[2])}`;
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
    <DemoFigure
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
    </DemoFigure>
  );
}

/**
 * Model spread — how much the currently visible models disagree, per day,
 * across the visible horizon. A band (per-day min/max across the selected
 * model curves) with the actuals drawn through it, plus the mean spread, the
 * widest-disagreement day, and the on-average-closest model. Recomputes from
 * the payload curves on every control change — model toggles and the horizon
 * slider both move it. With a single model selected the band is zero width by
 * definition, so the panel switches to that model's daily absolute error
 * bars; with none selected it audits the seasonal naive instead.
 */
export function ModelSpreadPanel({
  window,
  modelsOn,
  h,
  forecastDates,
}: {
  window: ForecastWindow;
  /** Currently visible model keys (any subset, any order). */
  modelsOn: string[];
  h: number;
  /** Forecast dates for the scored window (day labels). */
  forecastDates: string[];
}) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 110;
  const pad = { l: 34, r: 6, t: 6, b: 16 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;

  const days = Math.max(1, Math.min(h, window.actual.length));
  const selected = modelsOn.filter((m) => (window.curves[m]?.length ?? 0) >= days);
  const keys = selected.length > 0 ? selected : [NAIVE];
  const single = keys.length <= 1;
  const onlyKey = keys[0];

  // per-day min/max across the selected curves and the disagreement width
  const lo: number[] = [];
  const hi: number[] = [];
  for (let d = 0; d < days; d++) {
    const vals = keys
      .map((k) => window.curves[k][d])
      .filter((v): v is number => typeof v === "number");
    lo.push(vals.length ? Math.min(...vals) : 0);
    hi.push(vals.length ? Math.max(...vals) : 0);
  }
  const spread = hi.map((v, i) => v - lo[i]);
  const meanSpread = spread.reduce((s, v) => s + v, 0) / days;
  const widestDay = spread.reduce((best, v, i) => (v > spread[best] ? i : best), 0);
  // on-average-closest model across the window (mean absolute error)
  const leader = keys
    .map((k) => ({
      key: k,
      mae:
        window.curves[k].slice(0, days).reduce((s, v, i) => s + Math.abs(v - window.actual[i]), 0) /
        days,
    }))
    .sort((a, b) => a.mae - b.mae)[0];
  // single-model view: daily absolute error of that model
  const err = keys[0]
    ? window.curves[keys[0]].slice(0, days).map((v, i) => Math.abs(v - window.actual[i]))
    : [];

  const yMax = single
    ? Math.max(...err, 1) * 1.05
    : Math.max(...hi, ...window.actual.slice(0, days), 1) * 1.05;
  const slot = plotW / days;
  const barW = Math.min(slot * 0.5, 14);
  const px = (i: number) => pad.l + slot * i + slot / 2;
  const py = (v: number) => pad.t + plotH - (v / yMax) * plotH;
  const base = pad.t + plotH;
  const yTicks = [0, yMax / 2, yMax];

  const bandPath = single
    ? undefined
    : `M ${px(0)} ${py(lo[0])} ` +
      lo.slice(1).map((v, i) => `L ${px(i + 1)} ${py(v)}`).join(" ") +
      " " +
      hi.map((_, i) => `L ${px(days - 1 - i)} ${py(hi[days - 1 - i])}`).join(" ") +
      " Z";
  const actualPath = window.actual
    .slice(0, days)
    .map((v, i) => `${i === 0 ? "M" : "L"} ${px(i)} ${py(v)}`)
    .join(" ");

  return (
    <DemoFigure
      comment={
        single ? (
          <>
            Only {MODEL_LABELS[onlyKey]} is visible — a single model cannot disagree with itself, so
            the bars show its daily absolute error against the actuals (mean {leader.mae.toFixed(1)}
            ). Toggle another model on to see the spread band.
          </>
        ) : (
          <>
            The {keys.length} visible models disagree by {meanSpread.toFixed(1)} rentals/day on
            average — widest on {shortDate(forecastDates, widestDay)} at {spread[widestDay].toFixed(1)}
            — and {MODEL_LABELS[leader.key]} lands closest to the actuals across the window. The band
            is the selection's min/max, not a calibrated interval.
          </>
        )
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">
          {single ? `1 model — |error| view` : `${keys.length} models`}
        </span>
        <span className="chip demo-readout">
          {single ? `mean |err| ${leader.mae.toFixed(1)}` : `mean spread ${meanSpread.toFixed(1)}`}
        </span>
        <span className="chip demo-readout">
          {single
            ? `worst day ${shortDate(forecastDates, err.reduce((b, v, i) => (v > err[b] ? i : b), 0))}`
            : `widest ${shortDate(forecastDates, widestDay)}`}
        </span>
        {!single && (
          <span className="chip demo-readout">
            <span className="fwb-dot" style={{ background: MODEL_COLORS[leader.key] }} /> closest{" "}
            {MODEL_LABELS[leader.key]}
          </span>
        )}
      </div>
      <div ref={ref} className="wb-panel-viz">
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={
            single
              ? "daily absolute error of the visible model against actuals"
              : "per-day min/max spread across the visible models with actuals"
          }
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
          {single ? (
            err.map((v, i) => (
              <rect
                key={`e-${i}`}
                x={px(i) - barW / 2}
                y={py(v)}
                width={barW}
                height={Math.max(base - py(v), 0)}
                fill={MODEL_COLORS[onlyKey] ?? C_GRAY}
                opacity={0.85}
              >
                <title>{`day +${i + 1}: |err| ${v.toFixed(1)}`}</title>
              </rect>
            ))
          ) : (
            <path d={bandPath} fill="var(--secondary)" opacity={0.22} />
          )}
          <path d={actualPath} fill="none" stroke="var(--text)" strokeWidth={1.5} />
          {Array.from({ length: days }, (_, i) =>
            (i + 1) % 7 === 0 || i === days - 1 ? (
              <text key={`x-${i}`} x={px(i)} y={H - 4} textAnchor="middle" className="demo-axis-label">
                +{i + 1}
              </text>
            ) : null,
          )}
        </svg>
      </div>
    </DemoFigure>
  );
}


/**
 * Model verdict, comparative: one horizontal bar per active candidate —
 * window WAPE@h on a shared scale as a model-tinted bar (the seasonal naive
 * is the grey reference), the value label at the bar end, the best model's
 * bar crowned, and a right-aligned mini column of peak-day MAE — plus the
 * pooled committed chip at the full scored horizon. The footer names the
 * honest per-series outcome, including the intermittent case where the
 * naive wins.
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
    .map((m) => ({
      key: m,
      wape: wapeAt(window.actual, window.curves[m], h),
      peak: peakAbsError(window.actual, window.curves[m], h),
    }))
    .sort((a, b) => a.wape - b.wape);
  const bestKey = rows[0]?.key ?? null;
  const naiveWins = bestKey === NAIVE;
  const pooled = payload.groups.test_pooled;
  // committed pooled test bias per candidate — "—" when a curve has no
  // committed pooled row (never for the shipped candidates)
  const fmtBias = (key: string) => {
    const b = pooled[key]?.bias;
    return b === undefined ? "—" : `${b < 0 ? "−" : "+"}${Math.abs(b).toFixed(3)}`;
  };
  const committedChip =
    h === 28 && bestKey && bestKey !== NAIVE && pooled[bestKey] && pooled[NAIVE]
      ? pooled[bestKey].wrmsse - pooled[NAIVE].wrmsse
      : null;
  const intermWinRate =
    payload.groups.win_rate_vs_naive.convex_ensemble?.intermittent ?? null;

  // FIXED common scale: the maximum window WAPE@h across EVERY candidate
  // curve shipped in the payload for this series × origin — never recomputed
  // from the selected subset, so toggling a model never moves another bar's
  // width. Generous headroom (×1.22) keeps even the worst bar's value label
  // clear of the track end, so all bars compare on one basis with margins.
  const scaleMax = Math.max(...Object.values(window.curves).map((c) => wapeAt(window.actual, c, h)), 1e-6);
  const scale = scaleMax * 1.22;

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
    <DemoFigure comment={comment}>
      <div className="fwb-verdict">
        {rows.map((r) => {
          const pct = (r.wape / scale) * 100;
          return (
            <div
              key={r.key}
              className={`fwb-verdict-item ${r.key === bestKey ? "best" : ""}`}
            >
              <div className="fwb-verdict-row">
                <span className="fwb-verdict-name" title={MODEL_LABELS[r.key]}>
                  <span className="fwb-dot" style={{ background: MODEL_COLORS[r.key] }} />
                  {MODEL_LABELS[r.key]}
                  {r.key === bestKey && <span className="fwb-verdict-crown">best</span>}
                </span>
                <span className="fwb-bar-track">
                  <span
                    className="fwb-bar-fill"
                    style={{ width: `${pct.toFixed(1)}%`, backgroundColor: MODEL_COLORS[r.key] }}
                  />
                  <span className="fwb-bar-value" style={{ left: `calc(${pct.toFixed(1)}% + 6px)` }}>
                    {r.wape.toFixed(3)}
                  </span>
                </span>
                <span className="fwb-verdict-peak" title="peak-day MAE (worst single day)">
                  {r.peak.toFixed(1)}
                </span>
                <span
                  className="fwb-verdict-bias"
                  title="committed pooled test bias (mean forecast − actual share)"
                >
                  {fmtBias(r.key)}
                </span>
              </div>
            </div>
          );
        })}
        <div className="fwb-verdict-foot">
          {committedChip !== null && (
            <p className="fwb-verdict-committed">
              pooled official WRMSSE {committedChip > 0 ? "+" : "−"}
              {Math.abs(committedChip).toFixed(4)} committed
            </p>
          )}
          <p
            className="fwb-verdict-scale"
            title="maximum window WAPE@h across every candidate curve in the payload — the scale does not depend on the selected subset"
          >
            wape@{h}d scale max {scaleMax.toFixed(3)} · {Object.keys(window.curves).length}{" "}
            candidates · right columns: peak-day MAE, committed pooled bias
          </p>
        </div>
      </div>
    </DemoFigure>
  );
}
