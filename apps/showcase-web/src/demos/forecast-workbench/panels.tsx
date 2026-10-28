import type { ReactNode } from "react";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { CatalogEntry, ForecastWorkbenchPayload, ForecastWindow } from "../types";
import { C_GRAY, C_TEAL, MODELS } from "./chartData";
import {
  bandCalibration,
  bandWidthTrajectory,
  bucketedAbsError,
  peakAbsError,
  wapeAt,
  weekdayAbsError,
  weeklyAbsError,
  weeklyBandCoverage,
  worstBandMiss,
} from "./kpis";

const NAIVE = "seasonal_naive";
const MODEL_COLORS = Object.fromEntries(MODELS.map((m) => [m.key, m.color]));
const MODEL_LABELS = Object.fromEntries(MODELS.map((m) => [m.key, m.label]));
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WD_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

/** Compact "May 24" rendering of a forecast date; falls back to the day slot. */
function shortDate(dates: string[], day: number): string {
  const d = dates[day];
  const parts = d ? d.split("-") : [];
  if (parts.length !== 3) return `day +${day + 1}`;
  return `${MONTHS[Number(parts[1]) - 1] ?? parts[1]} ${Number(parts[2])}`;
}

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
 * Band calibration dashboard: the per-day hit strip (teal = actual inside
 * p10/p90, pink = outside, hover shows the day, band and actual), the width
 * trajectory across the horizon (uncertainty grows with lead time), weekly
 * coverage buckets showing where calibration drifts, the single worst band
 * violation, and the pooled committed coverage chip. Everything recomputes
 * client-side from the payload arrays for the selected series and horizon.
 * Collapses to a placeholder when LightGBM is deselected (the churn demo's
 * disabled-state pattern).
 */
export function BandCalibrationPanel({
  window,
  h,
  committedCoverage,
  forecastDates,
}: {
  window: ForecastWindow;
  h: number;
  /** Pooled committed 80% coverage across all 600 series (payload, fixed). */
  committedCoverage: number;
  /** Forecast dates for the current origin (labels hit-strip days / misses). */
  forecastDates: string[];
}) {
  const cal = bandCalibration(window, h);
  const weekly = weeklyBandCoverage(window, h);
  const widths = bandWidthTrajectory(window, h);
  const worst = worstBandMiss(window, h);

  // width-trajectory sparkline: container-measured like the other svg panels
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 300;
  const H = 34;
  const wMax = Math.max(...widths, 0);
  const wMin = Math.min(...widths, wMax);
  const span = Math.max(wMax - wMin, 1e-9);
  const px = (i: number) => (widths.length > 1 ? 4 + (i / (widths.length - 1)) * (W - 8) : W / 2);
  const py = (v: number) => 4 + (1 - (v - wMin) / span) * (H - 10);
  const pts = widths.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");

  const pctFmt = (f: number) => `${Math.round(f * 100)}%`;

  return (
    <Card
      comment={
        <>
          At this origin the committed 80% band catches {cal.hits} of {cal.n} scored days so far{" "}
          {cal.coverage >= 0.8 ? "at or above" : "just under"} its nominal level, averaging{" "}
          {cal.meanWidth.toFixed(1)} units wide
          {weekly.length > 1
            ? `; weekly coverage runs ${pctFmt(weekly[0])} → ${pctFmt(weekly[weekly.length - 1])} from week 1 to week ${weekly.length}`
            : `; the single visible week covers ${pctFmt(weekly[0] ?? cal.coverage)}`}
        </>
      }
    >
      <div className="demo-readouts">
        <span className={`chip demo-readout ${cal.coverage >= 0.75 ? "good" : "bad"}`}>
          {cal.hits}/{cal.n} days inside
        </span>
        <span className="chip demo-readout">mean width {cal.meanWidth.toFixed(1)}u</span>
        <span className="chip demo-readout">{(committedCoverage * 100).toFixed(1)}% committed</span>
      </div>
      <div className="fwb-band-dash">
        <div className="fwb-band-strip" role="img" aria-label="per-day band hit indicator">
          {Array.from({ length: cal.n }, (_, i) => {
            const hit = window.actual[i] >= window.band.p10[i] && window.actual[i] <= window.band.p90[i];
            return (
              <span
                key={i}
                className={`fwb-band-day ${hit ? "hit" : "miss"}`}
                title={`${shortDate(forecastDates, i)} (day +${i + 1}): ${
                  hit ? "inside" : "outside"
                } [${window.band.p10[i].toFixed(1)}, ${window.band.p90[i].toFixed(1)}] vs actual ${window.actual[i].toFixed(1)}`}
              />
            );
          })}
        </div>
        <div className="fwb-width-spark">
          <span className="fwb-mini-label">band width by horizon day (p90 − p10)</span>
          <div ref={ref} className="fwb-width-spark-viz">
            <svg
              width="100%"
              height={H}
              viewBox={`0 0 ${W} ${H}`}
              preserveAspectRatio="none"
              role="img"
              aria-label="mean band width by horizon day"
            >
              {pts && (
                <polygon points={`4,${H - 4} ${pts} ${(W - 4).toFixed(1)},${H - 4}`} fill={C_TEAL} opacity={0.12} />
              )}
              <polyline
                points={pts}
                fill="none"
                stroke={C_TEAL}
                strokeWidth={1.5}
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>
          <span className="fwb-spark-ends">
            <span>min {wMin.toFixed(1)}u</span>
            <span>max {wMax.toFixed(1)}u</span>
          </span>
        </div>
        <div className="fwb-cov-weeks" aria-label="weekly band coverage">
          {weekly.map((c, w) => (
            <div
              key={w}
              className="fwb-cov-week"
              title={`week ${w + 1}: ${pctFmt(c)} of days inside the band`}
            >
              <span className={`fwb-cov-box ${c >= 0.75 ? "" : "low"}`}>{pctFmt(c)}</span>
              <span className="fwb-cov-label">wk{w + 1}</span>
            </div>
          ))}
        </div>
        <p className="fwb-worst-miss">
          {worst
            ? `worst miss: ${shortDate(forecastDates, worst.day)} · actual ${worst.actual.toFixed(1)} vs ${
                worst.side === "over" ? "p90" : "p10"
              } ${worst.bound.toFixed(1)} (+${worst.amount.toFixed(1)})`
            : "no misses — every scored day sits inside the band"}
        </p>
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
 * Model verdict, comparative: one block per active candidate — dot, name,
 * window WAPE@h, delta chip, peak-day MAE — plus the row's error *shape* as a
 * 7-bucket |error| micro-bar profile, a total-|error| proportion bar so the
 * models' window totals are comparable at a glance, and a Mon..Sun heat-strip
 * of the primary model versus the seasonal-naive floor (hidden below 7 scored
 * days). The best model keeps the crown; the footer names the honest
 * per-series outcome, including the intermittent case where the naive wins.
 */
export function VerdictPanel({
  entry,
  window,
  modelsOn,
  h,
  payload,
  forecastDates,
}: {
  entry: CatalogEntry;
  window: ForecastWindow;
  modelsOn: string[];
  h: number;
  payload: ForecastWorkbenchPayload;
  /** Forecast dates for the current origin (weekday bucketing of |error|). */
  forecastDates: string[];
}) {
  const rows = modelsOn
    .filter((m) => window.curves[m])
    .map((m) => ({
      key: m,
      wape: wapeAt(window.actual, window.curves[m], h),
      buckets: bucketedAbsError(window.actual, window.curves[m], h),
      peak: peakAbsError(window.actual, window.curves[m], h),
      total: 0,
    }))
    .sort((a, b) => a.wape - b.wape);
  // micro-bar heights share one scale across rows so shapes are comparable
  const bucketMax = Math.max(1e-9, ...rows.flatMap((r) => r.buckets));
  for (const r of rows) r.total = r.buckets.reduce((s, v) => s + v, 0);
  const totalMax = Math.max(1e-9, ...rows.map((r) => r.total));
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

  // weekday heat-strip: the best candidate against the naive floor, only
  // once a full week of scored days is visible
  const nVisible = Math.max(0, Math.min(h, window.actual.length));
  const stripKey = bestKey && bestKey !== NAIVE && window.curves[bestKey] ? bestKey : null;
  const wdModel = stripKey ? weekdayAbsError(window.actual, window.curves[stripKey], forecastDates, h) : null;
  const wdNaive = window.curves[NAIVE]
    ? weekdayAbsError(window.actual, window.curves[NAIVE], forecastDates, h)
    : null;
  const showWeekstrip = nVisible >= 7 && wdModel !== null && wdNaive !== null;
  const wdMax = Math.max(1e-9, ...(wdModel ?? [0]), ...(wdNaive ?? [0]));
  const wdOpacity = (v: number) => (v > 0 ? 0.25 + 0.75 * (v / wdMax) : 0.08);
  const wdShare = (v: number) => `${((v / Math.max(wdModel!.reduce((s, x) => s + x, 0), 1e-9)) * 100).toFixed(0)}%`;

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
        <div className="fwb-verdict-head">
          <span>model</span>
          <span>|err| shape</span>
          <span>wape</span>
          <span>Δ vs naive</span>
          <span>peak</span>
        </div>
        {rows.map((r) => {
          const delta = (r.wape - naiveWape) * 100;
          const isNaiveRow = r.key === NAIVE;
          return (
            <div
              key={r.key}
              className={`fwb-verdict-item ${r.key === bestKey ? "best" : ""}`}
            >
              <div className="fwb-verdict-row">
                <span className="fwb-verdict-name">
                  <span className="fwb-dot" style={{ background: MODEL_COLORS[r.key] }} />
                  {MODEL_LABELS[r.key]}
                  {r.key === bestKey && <span className="fwb-verdict-crown">best</span>}
                </span>
                <span
                  className="fwb-microbars"
                  aria-hidden="true"
                  title={`${MODEL_LABELS[r.key]} |error| across 7 horizon buckets`}
                >
                  {r.buckets.map((v, i) => (
                    <span
                      key={i}
                      style={{
                        height: `${(v / bucketMax) * 100}%`,
                        background: v > 0 ? MODEL_COLORS[r.key] : "transparent",
                      }}
                    />
                  ))}
                </span>
                <span className="fwb-verdict-wape">{r.wape.toFixed(3)}</span>
                <span className={`chip demo-readout ${isNaiveRow ? "" : delta < 0 ? "good" : "bad"}`}>
                  {isNaiveRow ? "floor" : `${delta < 0 ? "−" : "+"}${Math.abs(delta).toFixed(1)} pts`}
                </span>
                <span className="fwb-verdict-peak" title="peak-day MAE (worst single day)">
                  {r.peak.toFixed(1)}
                </span>
              </div>
              <div
                className="fwb-verdict-share"
                role="img"
                aria-label={`${MODEL_LABELS[r.key]} total |error| for the window, share of the worst model`}
              >
                <span
                  style={{
                    width: `${(r.total / totalMax) * 100}%`,
                    background: MODEL_COLORS[r.key],
                  }}
                />
              </div>
            </div>
          );
        })}
        {showWeekstrip && (
          <div className="fwb-weekstrip">
            <span className="fwb-mini-label">
              weekday |error| — {MODEL_LABELS[stripKey!]} vs naive
            </span>
            <div className="fwb-weekstrip-row">
              <span className="fwb-weekstrip-tag">{MODEL_LABELS[stripKey!]}</span>
              {WD_LABELS.map((d, i) => (
                <span
                  key={d}
                  className="fwb-wd-cell"
                  style={{ background: MODEL_COLORS[stripKey!], opacity: wdOpacity(wdModel![i]) }}
                  title={`${d} · |err| ${wdModel![i].toFixed(1)} (${wdShare(wdModel![i])} of row)`}
                />
              ))}
            </div>
            <div className="fwb-weekstrip-row">
              <span className="fwb-weekstrip-tag">naive</span>
              {WD_LABELS.map((d, i) => (
                <span
                  key={d}
                  className="fwb-wd-cell"
                  style={{ background: C_GRAY, opacity: wdOpacity(wdNaive![i]) }}
                  title={`${d} · |err| ${wdNaive![i].toFixed(1)} (${(
                    (wdNaive![i] / Math.max(wdNaive!.reduce((s, x) => s + x, 0), 1e-9)) *
                    100
                  ).toFixed(0)}% of row)`}
                />
              ))}
            </div>
          </div>
        )}
        {!showWeekstrip && rows.length > 0 && nVisible < 7 && (
          <p className="fwb-wd-note">weekday breakdown needs at least 7 scored days</p>
        )}
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
