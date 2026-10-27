import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type {
  CatalogSeries,
  DemandClass,
  DemoManifest,
  ForecastPayload,
  ModelKey,
} from "../types";
import { DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import {
  bandAt,
  candidateAvailable,
  fmtDay,
  growthMaseAt,
  horizonKpi,
  mulberry32,
  originBlock,
  originDates,
  routedLabel,
  seedFromQuery,
  surprisePick,
} from "./kpis";
import { ExplorerPanel } from "./panels/ExplorerPanel";
import { ErrorAnalysisPanel } from "./panels/ErrorAnalysisPanel";
import { ReliabilityPanel } from "./panels/ReliabilityPanel";
import { ScoreboardPanel, modelDisableReason, peakStats } from "./panels/ScoreboardPanel";
import { Sparkline, useQueryParam } from "./panels/common";
import { MODEL_COLOR } from "./panels/ExplorerPanel";
import { fetchForecastPayload, fetchManifest } from "./payload";

const SHOCK_STOPS: readonly number[] = [0.5, 1, 1.5, 2];

const CLASSES: Array<DemandClass | "all"> = ["all", "lumpy", "erratic"];

const CANDIDATE_CHIPS = ["hurdle", "tweedie"] as const;

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, pick one of the three scored weekly origins, slide the true horizon h across the direct h-step forecasts, and shock the recent demand; watch the routed pipeline, the zero baseline, and the boosted per-horizon model respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "multi-step pooled MAE over the scored origins, routed pipeline vs all-HGB",
    value: "7.47 routed vs 11.71 all-HGB — the routed pipeline leads",
    ci: "routing lumpy series away from the boosted model wins +4.0 MAE [3.3, 4.8] (95% paired bootstrap over series × scored origins; 98.6% of series are lumpy; pooled rmae 0.649)",
  },
  scenarios: [
    { name: "base", controls: { horizon: 7, shock: 1 } },
    { name: "lumpy-series", controls: { horizon: 7, shock: 1 } },
    { name: "early-origin", controls: { horizon: 7, shock: 1 } },
    { name: "demand-shock", controls: { horizon: 7, shock: 2 } },
  ],
  live_endpoints: [
    {
      method: "POST",
      path: "/projects/02-demand-forecasting/forecast",
      label: "live what-if scoring",
      cost: "free-local",
    },
  ],
  payload: { path: "reports/demo_payload.json", schema_version: 3, required_keys: [] },
};

function signed(v: number, digits = 1): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;
}

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
  const hMax = payload.catalog_summary.horizon_days;
  const state = useControlState({ horizon: 7, shock: 1 }, manifest.scenarios);
  const { controls, setControl } = state;
  // snap the free numeric shock control to its discrete stops; the horizon
  // slider is continuous 1..hMax — every stop is a real direct-h model now
  const nearest = (v: number, stops: readonly number[]) =>
    stops.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a), stops[0]);
  const horizon = Math.min(hMax, Math.max(1, Math.round(controls.horizon ?? 7)));
  const shock = nearest(controls.shock ?? 1, SHOCK_STOPS);
  const dates = originDates(payload);
  const defaultDate = dates[dates.length - 1];

  // string controls serialize to the same query string as the numeric ones
  const defaultId = payload.catalog[0]?.series_id ?? "";
  const [seriesId, setSeriesId] = useQueryParam(
    "series",
    payload.catalog.map((s) => s.series_id),
    defaultId,
  );
  const [originDate, setOriginDate] = useQueryParam("origin", dates, defaultDate);
  const [modelRaw, setModel] = useQueryParam<ModelKey>(
    "model",
    ["zero", "routed", "champion", "hurdle", "tweedie", "adida"],
    "routed",
  );
  const series = payload.catalog.find((s) => s.series_id === seriesId) ?? payload.catalog[0];
  // coerce chips the current series can't serve: the boosted champion is
  // erratic-only; the peak-capable candidates only where the router
  // selected them (their curve IS the routed curve there); adida serves
  // every series
  const model: ModelKey =
    (modelRaw === "champion" && series.demand_class !== "erratic") ||
    ((modelRaw === "hurdle" || modelRaw === "tweedie") && !candidateAvailable(series, modelRaw))
      ? "routed"
      : modelRaw;
  const blk = originBlock(series, originDate);

  // --- decision layer τ (kept in the reliability panel)
  const [tau, setTau] = useState(0.9);

  // --- series picker filtering + stratified surprise-me
  const [clsFilter, setClsFilter] = useState<DemandClass | "all">("all");
  const [countryFilter, setCountryFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const countries = Object.keys(payload.catalog_summary.countries);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return payload.catalog.filter(
      (s) =>
        (clsFilter === "all" || s.demand_class === clsFilter) &&
        (countryFilter === "all" || s.country === countryFilter) &&
        (q === "" || s.label.toLowerCase().includes(q) || s.series_id.toLowerCase().includes(q)),
    );
  }, [payload.catalog, clsFilter, countryFilter, search]);

  const [seed, setSeed] = useState<number>(() => seedFromQuery() ?? 7);
  const surprise = () => {
    const next = seed + 1;
    const pick = surprisePick(filtered, mulberry32(next));
    if (pick) setSeriesId(pick.series_id);
    setSeed(next);
    try {
      const params = new URLSearchParams(window.location.search);
      params.set("seed", String(next));
      window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}${window.location.hash}`);
    } catch {
      /* URL state is a nicety */
    }
  };

  // --- error-click highlight (resets when the series or origin moves)
  const [highlightDay, setHighlightDay] = useState<number | null>(null);
  useEffect(() => {
    setHighlightDay(null);
  }, [series.series_id, originDate]);

  // --- KPIs at (origin, h) for the routed pipeline vs the zero baseline
  const routedKpi = horizonKpi(blk, "routed", shock, horizon);
  const zeroKpi = horizonKpi(blk, "zero", shock, horizon);
  const band = bandAt(payload.bands, horizon);

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="forecast-origin">
              Forecast origin
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="forecast-origin"
                  type="range"
                  className="wb-slider"
                  min={0}
                  max={dates.length - 1}
                  step={1}
                  value={dates.indexOf(originDate)}
                  style={{ "--fill": `${(dates.indexOf(originDate) / Math.max(1, dates.length - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setOriginDate(dates[Number(e.target.value)])}
                />
                <span className="chip wb-value-badge">
                  {fmtDay(blk?.origin_date ?? "")} — issued here
                </span>
              </div>
              <div className="wb-origin-stops">
                {dates.map((d) => (
                  <span key={d} className={`wb-origin-stop ${d === originDate ? "active" : ""}`}>
                    {fmtDay(d)}
                    {d === dates[dates.length - 1] && (
                      <span className="chip wb-origin-holdout">most recent scored origin</span>
                    )}
                  </span>
                ))}
              </div>
              <p className="demo-hint">
                issued {fmtDay(blk?.origin_date ?? "")} — direct h-step, scored once
              </p>
            </div>
          </div>
          <div className="wb-control-group wb-group-presets">
            <span className="wb-rail-title" id="model-chips-label">
              Model
            </span>
            <div className="demo-control">
              <div className="demo-presets" role="group" aria-labelledby="model-chips-label">
                <button
                  type="button"
                  className={`chip demo-preset ${model === "zero" ? "active" : ""}`}
                  aria-pressed={model === "zero"}
                  onClick={() => setModel("zero")}
                >
                  zero
                </button>
                <button
                  type="button"
                  className={`chip demo-preset ${model === "routed" ? "active" : ""}`}
                  aria-pressed={model === "routed"}
                  onClick={() => setModel("routed")}
                >
                  {routedLabel(series)}
                </button>
                <button
                  type="button"
                  className={`chip demo-preset ${model === "champion" ? "active" : ""}`}
                  aria-pressed={model === "champion"}
                  disabled={modelDisableReason(series, "champion") !== null}
                  title={
                    modelDisableReason(series, "champion") ??
                    "the boosted per-horizon direct HGB (erratic series)"
                  }
                  onClick={() => setModel("champion")}
                >
                  boosted HGB
                </button>
                {CANDIDATE_CHIPS.map((cand) => {
                  const reason = modelDisableReason(series, cand);
                  return (
                    <button
                      key={cand}
                      type="button"
                      className={`chip demo-preset ${model === cand ? "active" : ""}`}
                      aria-pressed={model === cand}
                      disabled={reason !== null}
                      title={reason ?? `the peak-capable ${cand} candidate (this series' method)`}
                      onClick={() => setModel(cand)}
                    >
                      {cand}
                    </button>
                  );
                })}
                <button
                  type="button"
                  className={`chip demo-preset ${model === "adida" ? "active" : ""}`}
                  aria-pressed={model === "adida"}
                  title="7-day-aggregate intermittent forecast distributed by weekday profile (wave 22)"
                  onClick={() => setModel("adida")}
                >
                  adida
                </button>
              </div>
              <p className="demo-hint">per-series routing picks the method on training origins</p>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="forecast-horizon">
              Horizon h
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="forecast-horizon"
                  type="range"
                  className="wb-slider"
                  min={1}
                  max={hMax}
                  step={1}
                  value={horizon}
                  style={{ "--fill": `${((horizon - 1) / Math.max(1, hMax - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("horizon", Number(e.target.value))}
                />
                <span className="chip wb-value-badge">{horizon}d</span>
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-slider">
            <label className="wb-rail-title" htmlFor="demand-shock">
              Demand shock
            </label>
            <div className="demo-control">
              <div className="wb-slider-row">
                <input
                  id="demand-shock"
                  type="range"
                  className="wb-slider"
                  min={0}
                  max={SHOCK_STOPS.length - 1}
                  step={1}
                  value={SHOCK_STOPS.indexOf(shock)}
                  style={{ "--fill": `${(SHOCK_STOPS.indexOf(shock) / (SHOCK_STOPS.length - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("shock", SHOCK_STOPS[Number(e.target.value)])}
                />
                <span className="chip wb-value-badge">×{shock.toFixed(1)}</span>
              </div>
              <p className="demo-hint">scales the last 7 days before the origin — exact re-scores</p>
            </div>
          </div>
          <div className="wb-control-group wb-group-picker">
            <span className="wb-rail-title" id="series-picker-label">
              Series catalog
            </span>
            <div className="demo-control">
              <input
                type="search"
                className="wb-series-search"
                placeholder="search country or product"
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
              <div className="wb-slider-row">
                <label className="wb-rail-title" htmlFor="country-filter">
                  country
                </label>
                <select
                  id="country-filter"
                  className="wb-series-search"
                  value={countryFilter}
                  onChange={(e) => setCountryFilter(e.target.value)}
                >
                  <option value="all">all countries</option>
                  {countries.map((c) => (
                    <option key={c} value={c}>
                      {c} ({payload.catalog_summary.countries[c]})
                    </option>
                  ))}
                </select>
                <button type="button" className="chip demo-preset" onClick={surprise}>
                  surprise me
                </button>
              </div>
              <ul className="wb-series-list" aria-label="Series list" style={{ maxHeight: 300 }}>
                {filtered.map((s) => (
                  <li key={s.series_id}>
                    <button
                      type="button"
                      className={`wb-series-row ${s.series_id === series.series_id ? "active" : ""}`}
                      aria-pressed={s.series_id === series.series_id}
                      onClick={() => setSeriesId(s.series_id)}
                    >
                      <Sparkline
                        values={(originBlock(s, originDate)?.history.y ?? []).slice(-30)}
                        color={MODEL_COLOR[model]}
                      />
                      <span className="wb-series-label">{s.label}</span>
                      <span className="chip wb-series-class">{s.demand_class}</span>
                    </button>
                  </li>
                ))}
                {filtered.length === 0 && <li className="wb-series-empty">no series matches</li>}
              </ul>
              <p className="demo-hint">
                {filtered.length} of {payload.catalog.length} series — surprise pick is
                class-stratified, seeded (?seed=)
              </p>
            </div>
          </div>
        </>
      }
      canvas={
        <ExplorerPanel
          series={series}
          origin={blk}
          model={model}
          horizon={horizon}
          shock={shock}
          highlightDay={highlightDay}
        />
      }
      kpis={
        <>
          <KpiTile
            label="MAE at origin + h"
            value={
              routedKpi && zeroKpi
                ? `${routedKpi.mae.toFixed(2)} vs ${zeroKpi.mae.toFixed(2)}`
                : "n/a"
            }
            sub={`routed vs zero · ${fmtDay(blk?.origin_date ?? "")} · h = ${horizon}`}
            tone={
              routedKpi && zeroKpi ? (routedKpi.mae <= zeroKpi.mae ? "good" : "bad") : "neutral"
            }
          />
          <KpiTile
            label="MASE at origin + h"
            value={
              routedKpi?.mase == null
                ? "n/a"
                : `${routedKpi.mase.toFixed(2)} vs ${zeroKpi?.mase != null ? zeroKpi.mase.toFixed(2) : "n/a"}`
            }
            sub={routedKpi?.mase == null ? "(zero-scale history)" : `scale: history seasonal-naive`}
            tone={
              routedKpi?.mase == null ? "neutral" : routedKpi.mase <= 1 ? "good" : "bad"
            }
          />
          <KpiTile
            label="Bias at origin + h"
            value={routedKpi ? signed(routedKpi.bias) : "n/a"}
            sub={
              routedKpi
                ? `units · ${routedKpi.bias > 0 ? "over" : routedKpi.bias < 0 ? "under" : "un"}-forecasts on day h · h = ${horizon}`
                : "no curve"
            }
            tone={
              routedKpi ? (routedKpi.bias > 0 ? "bad" : routedKpi.bias < 0 ? "good" : "neutral") : "neutral"
            }
          />
          <KpiTile
            label="WAPE at origin + h"
            value={routedKpi?.wape == null ? "n/a" : `${(routedKpi.wape * 100).toFixed(1)}%`}
            sub={`|err| / demand on day h · h = ${horizon}`}
          />
          <KpiTile
            label="Band coverage at h"
            value={
              band
                ? `${(band.coverage * 100).toFixed(1)}% vs ${(payload.bands.target_coverage * 100).toFixed(0)}%`
                : "n/a"
            }
            sub={
              band
                ? `${band.verdict} · avg width ${band.avgWidth.toFixed(2)} units (committed, pooled over scored origins)`
                : "no committed band"
            }
            tone={band ? (band.verdict === "calibrated" ? "good" : "neutral") : "neutral"}
          />
        </>
      }
      notice={
        <>
          <Notice>
            <ClassVerdictText payload={payload} series={series} />
          </Notice>
          <Notice>
            <HorizonTruthText payload={payload} h={horizon} />
          </Notice>
          {model === "adida" && shock !== 1 && (
            <Notice>
              <strong>adida ships without shock curves</strong> — the payload cap leaves room
              for three shock families, not four. The base (unshocked) ADIDA curve is shown;
              the routed / zero / floor curves still re-score exactly under ×{shock.toFixed(1)}.
            </Notice>
          )}
        </>
      }
      secondary={
        <>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">model scoreboard</h3>
            <ScoreboardPanel
              payload={payload}
              series={series}
              origin={blk}
              model={model}
              horizon={horizon}
              shock={shock}
              onPickModel={setModel}
            />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">error analysis</h3>
            <ErrorAnalysisPanel
              origin={blk}
              model={model}
              shock={shock}
              highlightDay={highlightDay}
              onHighlight={setHighlightDay}
            />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">reliability + decision</h3>
            <ReliabilityPanel
              payload={payload}
              series={series}
              origin={blk}
              horizon={horizon}
              tau={tau}
              onTau={setTau}
            />
          </div>
        </>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              <code className="wb-tag">routed pipeline</code> — per-series routing on the
              selection origins (committed table):{" "}
              {Object.entries(payload.catalog_summary.model_used_counts).map(([m, n]) => (
                <span key={m}>
                  <code className="wb-tag">{m}</code> ×{n}{" "}
                </span>
              ))}
              in the catalog. The seasonal-naive floor and the zero baseline grade every
              candidate.
            </p>
            {Object.entries(payload.catalog_summary.peak_capable_candidates ?? {}).map(
              ([name, desc]) => (
                <p className="wb-evidence-line" key={name}>
                  <code className="wb-tag">{name}</code> — {desc}
                </p>
              ),
            )}
            <p className="wb-evidence-line">{payload.catalog_summary.routing_rule}</p>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">{payload.evaluation_metadata.protocol}</span>
              <span className="wb-tag">
                {payload.evaluation_metadata.origins.n_origins} weekly origins
              </span>
              <span className="wb-tag">
                {payload.evaluation_metadata.origins.gap_days}d gap — window abuts the origin
              </span>
              <span className="wb-tag">
                h = {payload.evaluation_metadata.horizons[0]}–
                {payload.evaluation_metadata.horizons[payload.evaluation_metadata.horizons.length - 1]}{" "}
                direct horizons
              </span>
              <span className="wb-tag">{payload.headline.n_series_experiment} series</span>
            </p>
            <p className="wb-evidence-line">
              Features: {payload.evaluation_metadata.feature_semantics}
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">metrics results</h4>
            <p className="wb-evidence-line">
              {payload.headline.claim.charAt(0).toUpperCase() + payload.headline.claim.slice(1)}.
            </p>
            <p className="wb-evidence-line wb-metric-tags">
              {Object.entries(payload.headline.pooled_mae_by_model)
                .sort((a, b) => a[1] - b[1])
                .map(([name, v]) => (
                  <span key={name} className="wb-tag">
                    {name} {v.toFixed(2)}
                  </span>
                ))}
            </p>
            <p className="wb-evidence-line">
              Peak-day error (top-decile days, routed vs zero, per class):{" "}
              {Object.entries(payload.peak_capture.per_class).map(([cls, entry]) => {
                const stats = peakStats(entry, "routed");
                return stats ? (
                  <span key={cls} className="wb-tag">
                    {cls} {stats.peak_mae.toFixed(1)}
                  </span>
                ) : null;
              })}{" "}
              — {payload.peak_capture.bootstrap.method}.
            </p>
            <p className="wb-evidence-line">
              Bands: {(payload.bands.pooled_coverage * 100).toFixed(1)}% pooled coverage (target{" "}
              {(payload.bands.target_coverage * 100).toFixed(0)}%),{" "}
              {payload.bands.pooled_verdict} — {payload.bands.note}
            </p>
            <p className="wb-evidence-line">
              {payload.decision.label} — documented costs:{" "}
              {payload.decision.cost_assumptions.holding_cost_per_unit}/unit held,{" "}
              {payload.decision.cost_assumptions.stockout_cost_per_unit_short}/unit short (
              {payload.decision.cost_assumptions.cost_basis}); offsets are τ-quantiles of the
              policy's selection-origin residuals per class and horizon.
            </p>
            <p className="wb-evidence-line">
              Committed τ=0.90 per class:{" "}
              {Object.entries(payload.decision.per_class).map(([cls, byTau]) => {
                const row = byTau[`tau_${(0.9).toFixed(2)}`];
                if (!row) return null;
                return (
                  <span key={cls} className="wb-tag">
                    {cls}: routed {row.delta_champion_minus_floor >= 0 ? "above" : "below"} floor (
                    {row.delta_champion_minus_floor >= 0 ? "+" : ""}
                    {row.delta_champion_minus_floor.toFixed(1)})
                  </span>
                );
              })}
            </p>
            {payload.decision.newsvendor && (
              <NewsvendorBlock newsvendor={payload.decision.newsvendor} />
            )}
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The workbench replays a chosen point in history — nothing refits. The{" "}
              <strong>origin</strong> slider moves across three of the four scored weekly origins;
              the explorer shows only what was known as of that date — history up to the day
              before the origin — plus the 14 days that came after, as ghost actuals. Each curve
              is a set of <strong>direct h-step forecasts</strong>: one model per horizon
              h = 1…14 — every day of the window is a real direct model, so the{" "}
              <strong>horizon</strong> slider switches between genuinely different models at every
              stop and the error genuinely grows with h. The <strong>shock</strong>{" "}
              lever scales the last 7 days before the origin — the only demand signal these
              models read — with the re-scores precomputed offline, exactly.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              Daily demand for {payload.headline.n_series_experiment} country-product series from
              the UCI Online Retail II track under the{" "}
              <strong>{payload.evaluation_metadata.protocol}</strong> protocol:{" "}
              {payload.evaluation_metadata.origins.n_origins} weekly rolling origins (
              {payload.evaluation_metadata.origins.gap_days}-day gap — the forecast window starts
              the day after the origin, the 57-day nowcast hole is gone),{" "}
              {payload.evaluation_metadata.holdout_designation} Routing and the conformal widths
              were selected on the {payload.evaluation_metadata.origins.selection_dates.length}{" "}
              selection origins only; the last {payload.evaluation_metadata.origins.test_dates.length}{" "}
              were scored once and never read for selection.{" "}
              {payload.evaluation_metadata.target_definition}
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">honest limitation</h4>
            <p className="wb-evidence-line">
              {payload.dataset_metadata.zero_sales_caveat} The erratic class is 15 series —
              per-series claims there stay descriptive. The order-up-to layer is a simulation
              with documented costs, not a savings claim: on lumpy demand the routed policy
              costs more than the floor at the committed service levels. Inventory planning
              would still need per-series safety-stock calibration and a lead-time objective the
              experiment does not commit.
            </p>
          </div>
        </>
      }
    />
  );
}

/** Class-verdict notice: what serves this class and what the committed
 * peak-capture numbers say — erratic cites the peak-day win over zero,
 * lumpy the honest flat-vs-peak split. All numbers derive from the payload. */
function ClassVerdictText({ payload, series }: { payload: ForecastPayload; series: CatalogSeries }) {
  const peak = payload.peak_capture.per_class[series.demand_class];
  if (series.demand_class === "erratic") {
    const counts = payload.catalog.filter((s) => s.demand_class === "erratic").reduce(
      (acc, s) => {
        acc[s.model_used] = (acc[s.model_used] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
    const parts = Object.entries(counts)
      .map(([m, n]) => `${n} ${m.replace("_hgb", "").replace("hgb_", "")}`)
      .join(" · ");
    const zero = peakStats(peak, "zero");
    let best: { peak_mae: number; peak_mae_vs_zero?: { spans_zero: boolean } } | null = null;
    if (peak) {
      for (const c of payload.peak_capture.candidates) {
        const s = peakStats(peak, c);
        if (s && (best === null || s.peak_mae < best.peak_mae)) best = s;
      }
    }
    const est = best?.peak_mae_vs_zero && !best.peak_mae_vs_zero.spans_zero;
    return (
      <>
        <strong>Erratic series</strong> — all {seriesCount(payload, "erratic")} erratic series
        route to the peak-capable learners ({parts}, committed routing table). Peak-day error{" "}
        <strong>
          {zero ? zero.peak_mae.toFixed(0) : "n/a"} → ~{best ? best.peak_mae.toFixed(0) : "n/a"}
        </strong>{" "}
        vs the zero baseline — committed, paired CI {est ? "excludes zero" : "spans zero"}.
      </>
    );
  }
  const pooled = payload.headline.pooled_mae_by_model;
  const routedP = peakStats(peak, "routed");
  const tw = peakStats(peak, "hgb_tweedie");
  return (
    <>
      <strong>Lumpy series</strong> — flat methods keep the pooled lead (
      <strong>
        {pooled.routed?.toFixed(2)} vs tweedie {pooled.hgb_tweedie?.toFixed(2)}
      </strong>
      ); tweedie cuts peak-day error{" "}
      <strong>
        {routedP ? routedP.peak_mae.toFixed(1) : "n/a"} → {tw ? tw.peak_mae.toFixed(1) : "n/a"}
      </strong>{" "}
      but trades timing recall{" "}
      <strong>
        {routedP ? routedP.peak_recall.toFixed(2) : "n/a"} → {tw ? tw.peak_recall.toFixed(2) : "n/a"}
      </strong>
      . Both facts committed.
    </>
  );
}

function seriesCount(payload: ForecastPayload, cls: DemandClass): number {
  return payload.catalog.filter((s) => s.demand_class === cls).length;
}

/** The wave-22 newsvendor layer (revision 3.4): per class and service level,
 * the expected daily cost per unit-demand of ordering the routed band's
 * q-quantile vs the floor's seasonal-naive weekday quantile — documented
 * cost assumptions, a simulation, no savings claims. Compact table in the
 * evidence area, committed numbers only. */
function NewsvendorBlock({
  newsvendor,
}: {
  newsvendor: NonNullable<ForecastPayload["decision"]["newsvendor"]>;
}) {
  const costs = newsvendor.cost_assumptions;
  const classes = Object.keys(newsvendor.per_class);
  return (
    <>
      <p className="wb-evidence-line">
        <strong>Newsvendor order-quantile cost</strong> (wave 22) — order = the routed band's
        q-quantile (dense rows interpolate the committed p10/p50/p90 ladder; sparse rows the
        training-history ladder); the floor orders the same quantile of the seasonal-naive
        weekday distribution. Documented assumption: holding{" "}
        {costs.holding_cost_per_unit_ordered_unsold_per_day}/unit ordered-but-unsold/day,
        stockout {costs.stockout_cost_per_unit_short_per_day}/unit short/day — a simulation,
        no savings claims. Expected daily cost per unit-demand (committed, 95% paired
        bootstrap on the Δ):
      </p>
      <table className="data-table wb-cmp-table" aria-label="newsvendor cost per class">
        <thead>
          <tr>
            <th>class</th>
            {newsvendor.service_levels.map((q) => (
              <th key={q}>q={q.toFixed(2)} routed / floor</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {classes.map((cls) => (
            <tr key={cls}>
              <th>{cls}</th>
              {newsvendor.service_levels.map((q) => {
                const row = newsvendor.per_class[cls]?.[`q_${q.toFixed(2)}`];
                if (!row) return <td key={q}>n/a</td>;
                const diff = row.routed_minus_floor;
                return (
                  <td key={q}>
                    {row.routed_cost_per_unit_demand.toFixed(3)} /{" "}
                    {row.floor_cost_per_unit_demand.toFixed(3)}{" "}
                    <span
                      className={`chip demo-readout ${diff.spans_zero ? "" : "good"}`}
                      title={`95% CI [${diff.ci95[0].toFixed(3)}, ${diff.ci95[1].toFixed(3)}]`}
                    >
                      Δ {diff.diff >= 0 ? "+" : ""}
                      {diff.diff.toFixed(3)} {diff.spans_zero ? "(spans zero)" : "(established)"}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/** Horizon-truth notice: the error-growth story from the committed curves.
 * h=1 under weekly origins lands on a fixed near-zero weekday, so the honest
 * growth read is h=2 -> h=14 — quoted as MASE values, not a flashy ratio. */
function HorizonTruthText({ payload, h }: { payload: ForecastPayload; h: number }) {
  const mase2 = growthMaseAt(payload.horizon_growth, "champion", 2);
  const mase14 = growthMaseAt(payload.horizon_growth, "champion", 14);
  return (
    <>
      Error grows with horizon: committed MASE{" "}
      <strong>{mase2 !== null ? mase2.toFixed(2) : "n/a"}</strong> at h=2 to{" "}
      <strong>{mase14 !== null ? mase14.toFixed(2) : "n/a"}</strong> at h=14 (h=1 is a fixed
      near-zero weekday under weekly origins — the slider is real: each stop is a different
      direct model, and you are at <strong>h={h}</strong>).
    </>
  );
}
