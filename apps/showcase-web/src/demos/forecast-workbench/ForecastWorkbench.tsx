import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { forecastDemand } from "../../api";
import { LineChart, type LineMarker } from "../charts/LineChart";
import { useMeasuredSize } from "../charts/useMeasuredSize";
import type { CatalogSeries, DemoManifest, ForecastPayload } from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import {
  classPooledMase,
  coverageNote,
  deriveFeatures,
  fmtDay,
  historyPeak,
  LIVE_HORIZONS,
  maeAt,
  maseAt,
  representativeByClass,
  spikeDelta,
  windowMase,
} from "./kpis";
import { fetchForecastPayload, fetchManifest } from "./payload";

const C_TEAL = "#2dd4bf";
const C_AMBER = "#fbbf24";
const C_GRAY = "#64748b";
const C_WHITE = "#f8fafc";

const CLASSES: Array<CatalogSeries["demand_class"] | "all"> = [
  "all",
  "smooth",
  "intermittent",
  "sparse",
];

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, stretch the horizon, and stress the recent demand — watch the forecast, the band, and the baseline respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "MASE on real intermittent demand (1.0 = seasonal-naive parity)",
    value: "0.980 vs 1.117 naive",
    ci: "only the tuned HGB clears MASE 1",
  },
  scenarios: [
    { name: "base", controls: { series: "United Kingdom|85123A", horizon: 7, spike: 1.0 } },
    { name: "sparse-series", controls: { series: "United Kingdom|84077", horizon: 7, spike: 1.0 } },
    { name: "spike", controls: { series: "United Kingdom|85123A", horizon: 7, spike: 1.5 } },
  ],
  live_endpoints: [
    {
      method: "POST",
      path: "/projects/02-demand-forecasting/forecast",
      label: "live what-if scoring",
      cost: "free-local",
    },
  ],
  payload: { path: "reports/demo_payload.json", schema_version: 1, required_keys: [] },
};

/** Card with the shared figure-card chrome (chart region + commentary band). */
function Figure({ comment, children }: { comment: ReactNode; children: ReactNode }) {
  return (
    <div className="figure-card">
      {children}
      <footer className="figure-card-band">
        <p className="figure-comment">{comment}</p>
      </footer>
    </div>
  );
}

/** Tiny inline sparkline for picker rows and class tiles. */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const W = 64;
  const H = 20;
  const max = Math.max(...values, 1);
  const pts = values
    .map(
      (v, i) =>
        `${((i / Math.max(1, values.length - 1)) * W).toFixed(1)},${(
          H -
          (Math.max(0, v) / max) * (H - 2) -
          1
        ).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg width={W} height={H} className="wb-spark" aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

// --- fan chart (canvas) -------------------------------------------------------

type LiveState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; values: number[] }
  | { status: "unavailable" };

function FanPanel({
  series,
  horizon,
  spike,
  live,
}: {
  series: CatalogSeries;
  horizon: number;
  spike: number;
  live: LiveState;
}) {
  const histY = series.history.y;
  const n = histY.length;
  const fc = series.forecast;
  const span = fc.y_pred.length;
  const total = n + span;
  const H = Math.min(horizon, span);
  const origin = histY[n - 1];

  const nan = (k: number) => Array<number>(Math.max(0, k)).fill(NaN);
  // forecast-span series start at the origin (last actual) so they connect
  // to history; the NaN spans are segment breaks — LineChart renders each
  // contiguous run of finite values as its own polyline
  const champion = [...nan(n - 1), origin, ...fc.y_pred.slice(0, H), ...nan(span - H)];
  const naive = [...nan(n - 1), origin, ...fc.naive.slice(0, H), ...nan(span - H)];
  const actual = [...histY, ...nan(span)];
  const liveSeries =
    live.status === "ok"
      ? [...nan(n - 1), origin, ...live.values, ...nan(span - live.values.length)]
      : null;

  const seriesList = [
    { name: "champion", color: C_TEAL, values: champion },
    { name: "seasonal-naive", color: C_GRAY, dashed: true, values: naive },
    ...(liveSeries
      ? [{ name: "live re-score", color: C_AMBER, dashed: true, values: liveSeries }]
      : []),
    { name: "actual", color: C_WHITE, values: actual },
  ];

  const sliceMax = (arr: number[]) => Math.max(...arr.slice(0, H), 0);
  const cMax =
    Math.max(
      ...histY,
      sliceMax(fc.p90),
      sliceMax(fc.y_pred),
      sliceMax(fc.naive),
      live.status === "ok" ? Math.max(...live.values) : 0,
      1,
    ) * 1.08;

  const x = Array.from({ length: total }, (_, i) => i);
  const dates = (i: number) => (i < n ? series.history.dates[i] : fc.dates[i - n]);

  const markers: LineMarker[] = [{ xIndex: n - 1, label: "forecast origin", style: "dashed" }];

  // The p10/p90 band spans only the forecast days, so it can't ride the
  // NaN-gapped chart series — draw it on an overlay SVG with the same
  // padding/scale math as LineChart (pad + yMax passed explicitly).
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const pad = { l: 52, r: 18, t: 16, b: 32 };
  const W = size?.w ?? 720;
  const Hpx = size?.h ?? 280;
  const plotW = W - pad.l - pad.r;
  const plotH = Hpx - pad.t - pad.b;
  const px = (i: number) => pad.l + (i / (total - 1)) * plotW;
  const py = (v: number) => pad.t + plotH - (v / cMax) * plotH;
  const bandFwd = Array.from({ length: H + 1 }, (_, k) => {
    // day h sits at index n−1+h with band value h−1; the k=0 point anchors
    // the band at the origin with the day-1 width
    const i = n - 1 + k;
    return `${px(i).toFixed(1)},${py(fc.p90[Math.max(0, k - 1)]).toFixed(1)}`;
  });
  const bandBack = Array.from({ length: H + 1 }, (_, k) => {
    const i = n - 1 + (H - k);
    return `${px(i).toFixed(1)},${py(fc.p10[Math.max(0, H - k - 1)]).toFixed(1)}`;
  });

  const championMase = maseAt(series.errors, H);
  const naiveMase = maseAt(series.errors, H, "naive");

  return (
    <Figure
      comment={
        <>
          The champion point forecast with the committed p10–p90 backtest band against the
          weekly seasonal-naive floor; the dashed line marks the forecast origin, history is
          the last {n} committed days.
          {live.status === "ok" && (
            <> The amber dashes are live re-scores of the first {LIVE_HORIZONS.length} days
            with the recent-demand spike applied.</>
          )}
        </>
      }
    >
      <div className="demo-readouts">
        <span className="chip demo-readout">{series.label}</span>
        <span className="chip demo-readout">{series.demand_class}</span>
        <span className="chip demo-readout">horizon {H}d</span>
        <span className="chip demo-readout">spike ×{spike.toFixed(1)}</span>
        {championMase === null ? (
          <span className="chip demo-readout">MASE n/a — zero-scale series</span>
        ) : (
          <span className={`chip demo-readout ${championMase < 1 ? "good" : "bad"}`}>
            MASE {championMase.toFixed(2)} — {championMase < 1 ? "beats" : "trails"} naive
            {naiveMase !== null && ` (${naiveMase.toFixed(2)})`}
          </span>
        )}
      </div>
      <div className="demo-chart">
        <div ref={ref} className="wb-fan">
          <LineChart
            x={x}
            series={seriesList}
            yMax={cMax}
            pad={pad}
            markers={markers}
            xTicks={6}
            formatX={(i) => fmtDay(dates(Math.round(i)))}
            ariaLabel="daily demand with forecast fan"
          />
          <svg
            className="wb-fan-band"
            width="100%"
            height="100%"
            viewBox={`0 0 ${W} ${Hpx}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d={`M${bandFwd.join(" L")} L${bandBack.join(" L")} Z`} fill={C_TEAL} fillOpacity={0.15} />
          </svg>
        </div>
      </div>
      <p className="demo-hint">
        {live.status === "ok"
          ? `amber fan: live re-score (h=1–${LIVE_HORIZONS.length}); band shows the committed backtest`
          : live.status === "loading"
            ? "re-scoring the next days live…"
            : "history in white, champion in teal, seasonal-naive dashed"}
      </p>
    </Figure>
  );
}

// --- secondary panels ---------------------------------------------------------

/** Per-horizon MAE, champion vs seasonal-naive, grouped bars on a static max. */
function ErrorByHorizonPanel({ series }: { series: CatalogSeries }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 90;
  const champ = series.errors.champion.mae;
  const naive = series.errors.naive.mae;
  const max = Math.max(...champ, ...naive, 1);
  const pad = 10;
  const labelH = 14;
  const plotH = H - pad * 2 - labelH;
  const groupW = (W - pad * 2) / champ.length;
  const barW = Math.max(1, groupW * 0.32);
  return (
    <Figure
      comment={
        <>
          Per-horizon absolute error on the committed backtest window — the champion's edge
          is widest where demand is regular, and thins on the zero-heavy tail.
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
          aria-label="absolute error by forecast horizon"
        >
          {champ.map((c, i) => {
            const n = naive[i] ?? 0;
            const x0 = pad + i * groupW;
            const cw = (c / max) * plotH;
            const nw = (n / max) * plotH;
            const base = pad + plotH;
            return (
              <g key={i}>
                <rect x={x0 + groupW / 2 - barW - 1} y={base - cw} width={barW} height={cw} fill={C_TEAL} opacity={0.85} />
                <rect x={x0 + groupW / 2 + 1} y={base - nw} width={barW} height={nw} fill={C_GRAY} opacity={0.8} />
                {(i === 0 || i === champ.length - 1) && (
                  <text x={x0 + groupW / 2} y={H - 2} textAnchor="middle" className="demo-axis-label">
                    h={i + 1}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="demo-hint">
        <span className="wb-legend-swatch" style={{ background: C_TEAL }} /> champion{" "}
        <span className="wb-legend-swatch" style={{ background: C_GRAY }} /> seasonal-naive
      </p>
    </Figure>
  );
}

/** Pooled window MASE by demand class, champion vs naive (static max bars). */
function ClassModelPanel({ payload }: { payload: ForecastPayload }) {
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const W = size?.w ?? 360;
  const H = size?.h ?? 90;
  const classes: CatalogSeries["demand_class"][] = ["smooth", "intermittent", "sparse"];
  const rows = classes.map((cls) => ({
    cls,
    champion: classPooledMase(payload.catalog, cls),
    naive: classPooledMase(payload.catalog, cls, "naive"),
  }));
  const max = Math.max(...rows.flatMap((r) => [r.champion ?? 0, r.naive ?? 0]), 1);
  const pad = 14;
  const labelW = 78;
  const barX = pad + labelW;
  const barW = W - barX - pad - 46;
  const rowH = H / rows.length;
  return (
    <Figure
      comment={
        <>
          Pooled window MASE by demand class — the margin over the weekly naive thins as
          zero days dominate, which is exactly where MASE 1 stops being easy.
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
          aria-label="pooled MASE by demand class"
        >
          {rows.map((r, i) => {
            const cy = rowH * i + rowH / 2;
            return (
              <g key={r.cls}>
                <text x={pad} y={cy - 4} className="demo-axis-label">
                  {r.cls}
                </text>
                <rect x={barX} y={cy - 12} width={barW} height={10} fill="var(--bg)" stroke="var(--border)" />
                <rect
                  x={barX}
                  y={cy - 12}
                  width={((r.champion ?? 0) / max) * barW}
                  height={10}
                  fill={C_TEAL}
                  opacity={0.9}
                />
                <rect x={barX} y={cy + 2} width={barW} height={10} fill="var(--bg)" stroke="var(--border)" />
                <rect
                  x={barX}
                  y={cy + 2}
                  width={((r.naive ?? 0) / max) * barW}
                  height={10}
                  fill={C_GRAY}
                  opacity={0.8}
                />
                <text x={W - pad} y={cy - 2} textAnchor="end" className="demo-axis-label">
                  {r.champion === null ? "n/a" : r.champion.toFixed(2)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="demo-hint">
        <span className="wb-legend-swatch" style={{ background: C_TEAL }} /> champion{" "}
        <span className="wb-legend-swatch" style={{ background: C_GRAY }} /> seasonal-naive
      </p>
    </Figure>
  );
}

/** One representative (highest-volume) series per class; click to load it. */
function ClassExplorerPanel({
  payload,
  activeId,
  onPick,
}: {
  payload: ForecastPayload;
  activeId: string;
  onPick: (seriesId: string) => void;
}) {
  const reps = representativeByClass(payload.catalog);
  return (
    <Figure
      comment={
        <>
          One representative series per demand class, with its committed window MASE — click
          a tile to load it into the workbench.
        </>
      }
    >
      <div className="wb-class-tiles">
        {(["smooth", "intermittent", "sparse"] as const).map((cls) => {
          const s = reps[cls];
          if (!s) return null;
          const m = windowMase(s.errors);
          return (
            <button
              key={cls}
              type="button"
              className={`wb-class-tile ${s.series_id === activeId ? "active" : ""}`}
              onClick={() => onPick(s.series_id)}
              aria-pressed={s.series_id === activeId}
            >
              <span className="wb-class-tile-head">
                <span className="chip">{cls}</span>
                <span className="wb-class-tile-mase">
                  {m === null ? "MASE n/a" : `MASE ${m.toFixed(2)}`}
                </span>
              </span>
              <Sparkline values={s.history.y.slice(-30)} color={C_TEAL} />
              <span className="wb-class-tile-label">{s.label}</span>
            </button>
          );
        })}
      </div>
    </Figure>
  );
}

// --- notice tiles -------------------------------------------------------------

/** Demand-class verdict from the selected series' committed window MASE. */
function ClassVerdictText({ series }: { series: CatalogSeries }) {
  const m = windowMase(series.errors);
  if (m === null) {
    return (
      <>
        Sparse, mostly-zero series — MASE is undefined on a{" "}
        <strong>zero seasonal scale</strong>; here the band, not the point, is the honest
        signal
      </>
    );
  }
  const pct = Math.round(Math.abs(1 - m) * 100);
  const maseStr = m.toFixed(2);
  const beats = m < 1;
  if (series.demand_class === "smooth") {
    return (
      <>
        Smooth series — the champion {beats ? "beats" : "trails"} the weekly pattern by{" "}
        <strong>{pct}%</strong> (MASE <strong>{maseStr}</strong>)
      </>
    );
  }
  if (series.demand_class === "intermittent") {
    return (
      <>
        Intermittent — the naive baseline is the one to beat; the champion{" "}
        {beats ? (
          <>
            clears MASE 1 (MASE <strong>{maseStr}</strong>)
          </>
        ) : (
          <>
            cannot clear MASE 1 here (MASE <strong>{maseStr}</strong>)
          </>
        )}
      </>
    );
  }
  return (
    <>
      Sparse series — mostly zero days, and the champion{" "}
      {beats ? (
        <>
          still clears MASE 1 by <strong>{pct}%</strong> (MASE <strong>{maseStr}</strong>)
        </>
      ) : (
        <>
          misses MASE 1 (MASE <strong>{maseStr}</strong>) — trust the band
        </>
      )}
    </>
  );
}

/** Spike-reaction tile: live h=1 re-score vs the committed day-1 forecast. */
function SpikeText({
  series,
  spike,
  live,
  spikeDisabled,
}: {
  series: CatalogSeries;
  spike: number;
  live: LiveState;
  spikeDisabled: boolean;
}) {
  if (spikeDisabled) {
    return (
      <>
        Live re-scoring is unavailable — the spike lever is off and the committed backtest
        stays on
      </>
    );
  }
  if (spike === 1) {
    return (
      <>
        No recent spike applied — push the lever and the next{" "}
        <strong>{LIVE_HORIZONS.length} days</strong> re-score live against the committed
        backtest
      </>
    );
  }
  if (live.status === "ok") {
    const committed = series.forecast.y_pred[0];
    const { pct } = spikeDelta(live.values[0], committed);
    return (
      <>
        A <strong>×{spike.toFixed(1)}</strong> recent spike{" "}
        {pct >= 0 ? "lifts" : "pulls down"} the next-day forecast from{" "}
        <strong>{Math.round(committed)}</strong> to <strong>{Math.round(live.values[0])}</strong>{" "}
        units (<strong>{pct >= 0 ? "+" : ""}{Math.round(pct)}%</strong>)
      </>
    );
  }
  if (live.status === "loading") {
    return (
      <>
        Re-scoring the next <strong>{LIVE_HORIZONS.length} days</strong> live with a{" "}
        <strong>×{spike.toFixed(1)}</strong> recent spike…
      </>
    );
  }
  return <>Live re-score failed — the committed backtest stays on</>;
}

// --- demo -------------------------------------------------------------------------

export default function ForecastWorkbench() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<ForecastPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchManifest("forecast-workbench")
      .then((m) => !cancelled && setManifest(m))
      .catch(() => {
        /* payload fetch below reports the real error */
      });
    fetchForecastPayload("forecast-workbench")
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
  return <Workbench manifest={manifest ?? FALLBACK_MANIFEST} payload={payload} />;
}

/** Workbench body once the payload (and manifest, or fallback) is in hand. */
function Workbench({ manifest, payload }: { manifest: DemoManifest; payload: ForecastPayload }) {
  const state = useControlState({ horizon: 7, spike: 1.0 }, manifest.scenarios);
  const { controls, setControl } = state;
  const horizon = controls.horizon ?? 7;
  const spike = controls.spike ?? 1.0;

  // the series control is a string, so it sits next to (not inside) the
  // numeric control state; the URL param round-trips the same way
  const defaultId = payload.catalog[0]?.series_id ?? "";
  const [seriesId, setSeriesIdState] = useState(() => {
    const q = new URLSearchParams(window.location.search).get("series");
    return q && payload.catalog.some((s) => s.series_id === q) ? q : defaultId;
  });
  const setSeriesId = (id: string) => {
    setSeriesIdState(id);
    try {
      const params = new URLSearchParams(window.location.search);
      if (id === defaultId) params.delete("series");
      else params.set("series", id);
      const qs = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash);
    } catch {
      // URL state is a nicety, never a crash
    }
  };
  const series =
    payload.catalog.find((s) => s.series_id === seriesId) ?? payload.catalog[0];

  // --- series picker filtering
  const [clsFilter, setClsFilter] = useState<"all" | CatalogSeries["demand_class"]>("all");
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return payload.catalog.filter(
      (s) =>
        (clsFilter === "all" || s.demand_class === clsFilter) &&
        (q === "" || s.label.toLowerCase().includes(q) || s.series_id.toLowerCase().includes(q)),
    );
  }, [payload.catalog, clsFilter, search]);

  // --- live spike re-scoring (bounded: one call per horizon for h=1..3)
  const [live, setLive] = useState<LiveState>({ status: "idle" });
  const [spikeDisabled, setSpikeDisabled] = useState(false);
  useEffect(() => {
    if (spike === 1 || spikeDisabled) {
      setLive({ status: "idle" });
      return;
    }
    let cancelled = false;
    setLive({ status: "loading" });
    const timer = window.setTimeout(() => {
      Promise.all(
        LIVE_HORIZONS.map((h) => forecastDemand(payload.project, series.series_id, deriveFeatures(series, h, spike))),
      )
        .then((rs) => {
          if (cancelled) return;
          setLive({ status: "ok", values: rs.map((r) => r.forecast) });
        })
        .catch(() => {
          if (cancelled) return;
          // churn-scorer pattern: a serving failure disables the lever
          setLive({ status: "unavailable" });
          setSpikeDisabled(true);
          setControl("spike", 1);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series.series_id, spike, spikeDisabled]);

  // --- KPIs
  const championMase = maseAt(series.errors, horizon);
  const naiveMase = maseAt(series.errors, horizon, "naive");
  const championMae = maeAt(series.errors, horizon);
  const naiveMae = maeAt(series.errors, horizon, "naive");
  const coverage = coverageNote(payload);
  const peak = historyPeak(series);

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-picker">
            <span className="wb-rail-title" id="series-picker-label">
              Series catalog
            </span>
            <div className="demo-control">
              <input
                type="search"
                className="wb-series-search"
                placeholder="search store or product"
                aria-label="Search series"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="demo-presets wb-class-filter" role="group" aria-label="Filter by demand class">
                {CLASSES.map((cls) => (
                  <button
                    key={cls}
                    type="button"
                    className={`chip demo-preset ${clsFilter === cls ? "active" : ""}`}
                    aria-pressed={clsFilter === cls}
                    onClick={() => setClsFilter(cls)}
                  >
                    {cls}
                  </button>
                ))}
              </div>
              <ul className="wb-series-list" aria-label="Series list" style={{ maxHeight: 340 }}>
                {filtered.map((s) => (
                  <li key={s.series_id}>
                    <button
                      type="button"
                      className={`wb-series-row ${s.series_id === series.series_id ? "active" : ""}`}
                      aria-pressed={s.series_id === series.series_id}
                      onClick={() => setSeriesId(s.series_id)}
                    >
                      <Sparkline values={s.history.y.slice(-30)} color={C_TEAL} />
                      <span className="wb-series-label">{s.label}</span>
                      <span className="chip wb-series-class">{s.demand_class}</span>
                    </button>
                  </li>
                ))}
                {filtered.length === 0 && <li className="wb-series-empty">no series matches</li>}
              </ul>
              <p className="demo-hint">
                {filtered.length} of {payload.catalog.length} series
              </p>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="forecast-horizon">
              Forecast horizon
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="forecast-horizon"
                  type="range"
                  className="wb-slider"
                  min={1}
                  max={payload.scalars.catalog_summary.horizon_days}
                  step={1}
                  value={horizon}
                  style={{ "--fill": `${((horizon - 1) / (payload.scalars.catalog_summary.horizon_days - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("horizon", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{horizon}d</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="demand-spike">
              Recent demand spike
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="demand-spike"
                  type="range"
                  className="wb-slider"
                  min={0.5}
                  max={1.5}
                  step={0.1}
                  value={spike}
                  disabled={spikeDisabled}
                  style={{ "--fill": `${((spike - 0.5) / 1) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("spike", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">×{spike.toFixed(1)}</span>
              </div>
              <p className="demo-hint">scales the lag features, re-scored live</p>
              {spikeDisabled && (
                <p className="state-box demo-score-note">
                  Live re-scoring unavailable — spike lever disabled, committed backtest shown
                </p>
              )}
            </div>
          </div>
        </>
      }
      canvas={<FanPanel series={series} horizon={horizon} spike={spike} live={live} />}
      kpis={
        <>
          <KpiTile
            label="MASE at horizon"
            value={
              championMase === null
                ? "n/a"
                : `${championMase.toFixed(2)} vs ${naiveMase?.toFixed(2) ?? "n/a"}`
            }
            sub={
              championMase === null
                ? "(zero-demand series)"
                : `champion vs seasonal-naive · h=${horizon}d`
            }
            tone={championMase === null ? "neutral" : championMase < 1 ? "good" : "bad"}
          />
          <KpiTile
            label="MAE at horizon"
            value={
              championMae === null
                ? "n/a"
                : `${championMae.toFixed(1)} vs ${naiveMae?.toFixed(1) ?? "n/a"}`
            }
            sub={`units · h=${horizon}d`}
          />
          <KpiTile label="band coverage" value={coverage.value} sub={coverage.sub} />
          <KpiTile
            label="history peak"
            value={peak ? String(peak.value) : "n/a"}
            sub={peak ? fmtDay(peak.date) : "no history"}
          />
        </>
      }
      notice={
        <>
          <Notice>
            <ClassVerdictText series={series} />
          </Notice>
          <Notice>
            <SpikeText series={series} spike={spike} live={live} spikeDisabled={spikeDisabled} />
          </Notice>
        </>
      }
      secondary={
        <>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">error by horizon</h3>
            <ErrorByHorizonPanel series={series} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">champion vs naive by class</h3>
            <ClassModelPanel payload={payload} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">class explorer</h3>
            <ClassExplorerPanel payload={payload} activeId={series.series_id} onPick={setSeriesId} />
          </div>
        </>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              <code className="wb-tag">{payload.scalars.models.champion}</code> — the committed
              backtest champion (one global pooled model;{" "}
              {payload.scalars.models.naive} is the weekly floor).
            </p>
            <p className="wb-evidence-line">{payload.scalars.models.selection_rule}</p>
            <p className="wb-evidence-line">
              Features: {payload.scalars.feature_schema.note} Calendar:{" "}
              {payload.scalars.feature_schema.calendar.join(", ")}; lags:{" "}
              {payload.scalars.feature_schema.lags.join(", ")}.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">metrics results</h4>
            <p className="wb-evidence-line">
              {payload.scalars.headline.claim.charAt(0).toUpperCase() +
                payload.scalars.headline.claim.slice(1)}
              .
            </p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">
                pooled mase {payload.scalars.headline.champion_mase.toFixed(4)}
              </span>
              <span className="wb-tag">
                naive {payload.scalars.headline.naive_mase.toFixed(4)}
              </span>
              {payload.scalars.band && (
                <>
                  <span className="wb-tag">
                    band coverage {(payload.scalars.band.quantile_coverage_pooled * 100).toFixed(1)}%
                  </span>
                  <span className="wb-tag">
                    target {Math.round(payload.scalars.band.target_coverage * 100)}%
                  </span>
                </>
              )}
            </p>
            {payload.scalars.band && (
              <p className="wb-evidence-line">{payload.scalars.band.note}.</p>
            )}
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              Each store-product series carries a committed 14-day backtest window: the
              champion point forecast, a p10–p90 quantile band, and the seasonal-naive floor.
              The <strong>horizon</strong> slider stretches how much of that window is shown;
              the <strong>spike</strong> lever re-scores the first days live through the
              served model.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              Daily demand for {payload.catalog.length} store-product series from the UCI
              Online Retail II track, backtest on committed expanding windows with embargo.
              The target is pooled{" "}
              <span className="wb-tag">MASE &lt; 1</span> — beating the weekly seasonal naive —
              on real intermittent demand.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">transfer-honesty caveat</h4>
            <p className="wb-evidence-line">
              These rankings are committed on <strong>real intermittent demand</strong>. A
              model ranked on smooth synthetic series would not transfer here: the sparse,
              mostly-zero class has no meaningful point-forecast MASE at all, and the band is
              the honest signal — treat any "winner" that skips intermittent demand as
              unproven.
            </p>
          </div>
        </>
      }
    />
  );
}
