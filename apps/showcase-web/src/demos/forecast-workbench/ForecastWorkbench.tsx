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
  fmtDay,
  growthRatio,
  horizonKpi,
  mulberry32,
  originBlock,
  originDates,
  routedLabel,
  scoreboardRow,
  seedFromQuery,
  surprisePick,
} from "./kpis";
import { ExplorerPanel, MODEL_COLOR } from "./panels/ExplorerPanel";
import { ModelComparisonPanel } from "./panels/ModelComparisonPanel";
import { ErrorAnalysisPanel } from "./panels/ErrorAnalysisPanel";
import { ReliabilityPanel } from "./panels/ReliabilityPanel";
import { Sparkline, useQueryParam } from "./panels/common";
import { fetchForecastPayload, fetchManifest } from "./payload";

const TABS = ["model comparison", "error analysis", "uncertainty & reliability"] as const;
type Tab = (typeof TABS)[number];

const SHOCK_STOPS: readonly number[] = [0.5, 1, 1.5, 2];

const CLASSES: Array<DemandClass | "all"> = ["all", "lumpy", "erratic"];

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series, pick one of the three scored weekly origins, slide the true horizon h across the direct h-step forecasts, and shock the recent demand; watch the routed pipeline, the zero baseline, and — on the 15 erratic series — the boosted per-horizon model respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser", "live"],
  hero: {
    label: "multi-step pooled MAE over the scored origins, routed pipeline vs all-HGB",
    value: "7.48 routed vs 12.06 all-HGB — the routed pipeline leads",
    ci: "routing lumpy series away from the boosted model wins +4.6 MAE [4.2, 5.1] (95% paired bootstrap over series x scored origins; 98.6% of series are lumpy)",
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
  const hLattice = payload.catalog_summary.horizons;
  const state = useControlState({ horizon: 7, shock: 1 }, manifest.scenarios);
  const { controls, setControl } = state;
  // snap the free numeric controls to their discrete stops
  const nearest = (v: number, stops: readonly number[]) =>
    stops.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a), stops[0]);
  const horizon = nearest(controls.horizon ?? 7, hLattice);
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
    ["zero", "routed", "champion"],
    "routed",
  );
  const series = payload.catalog.find((s) => s.series_id === seriesId) ?? payload.catalog[0];
  // the boosted champion is erratic-only; on a lumpy series it is routed away
  const model: ModelKey =
    modelRaw === "champion" && series.demand_class !== "erratic" ? "routed" : modelRaw;
  const blk = originBlock(series, originDate);

  // --- decision layer τ (kept in the reliability tab)
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

  // --- secondary band tabs + error-click highlight
  const [tab, setTab] = useState<Tab>("model comparison");
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
                Three of the four scored weekly test origins — direct h-step forecasts issued on
                these dates and scored once, never read for selection
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
                  disabled={series.demand_class !== "erratic"}
                  title={
                    series.demand_class !== "erratic"
                      ? "boosted models don't serve lumpy series — see the routing note"
                      : "the boosted per-horizon HGB (this series is erratic)"
                  }
                  onClick={() => setModel("champion")}
                >
                  champion
                </button>
              </div>
              <p className="demo-hint">
                {series.demand_class === "erratic"
                  ? "this series is erratic — the boosted per-horizon HGB serves it"
                  : `this series is lumpy — the boosted model is routed away; ${series.model_used} serves it (committed routing table)`}
              </p>
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
                  min={0}
                  max={hLattice.length - 1}
                  step={1}
                  value={hLattice.indexOf(horizon)}
                  style={{ "--fill": `${(hLattice.indexOf(horizon) / Math.max(1, hLattice.length - 1)) * 100}%` } as CSSProperties}
                  onChange={(e) => setControl("horizon", hLattice[Number(e.target.value)])}
                />
                <span className="chip wb-value-badge">h = {horizon}</span>
              </div>
              <p className="demo-hint">
                discrete stops on the committed lattice — each h is a different direct model, and
                the error genuinely grows (see the horizon-truth note)
              </p>
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
              <p className="demo-hint">
                scales the last 7 days before the origin — the demand signal every candidate reads
                (statistical curves re-fit offline, boosted curves re-scored through their fitted
                trees; exact, precomputed)
              </p>
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
                {filtered.length} of {payload.catalog.length} series — every erratic series is in
                the catalog (the boosted model only serves those); the surprise pick is
                class-stratified and seeded (?seed=)
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
            sub={`routed vs zero · ${fmtDay(blk?.origin_date ?? "")} · h ≤ ${horizon}`}
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
                ? `units · ${routedKpi.bias > 0 ? "over" : routedKpi.bias < 0 ? "under" : "un"}-forecasts on average · h ≤ ${horizon}`
                : "no curve"
            }
            tone={
              routedKpi ? (routedKpi.bias > 0 ? "bad" : routedKpi.bias < 0 ? "good" : "neutral") : "neutral"
            }
          />
          <KpiTile
            label="WAPE at origin + h"
            value={routedKpi?.wape == null ? "n/a" : `${(routedKpi.wape * 100).toFixed(1)}%`}
            sub={`Σ|err| / Σ demand · h ≤ ${horizon}`}
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
        </>
      }
      secondary={
        <div className="wb-secondary-panel wb-secondary-wide">
          <div className="wb-tabs" role="tablist" aria-label="Secondary views">
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                className={`chip wb-tab ${tab === t ? "active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="wb-tab-body">
            {tab === "model comparison" && (
              <ModelComparisonPanel
                payload={payload}
                series={series}
                origin={blk}
                model={model}
                horizon={horizon}
                shock={shock}
                onPickModel={setModel}
              />
            )}
            {tab === "error analysis" && (
              <ErrorAnalysisPanel
                origin={blk}
                model={model}
                shock={shock}
                highlightDay={highlightDay}
                onHighlight={setHighlightDay}
              />
            )}
            {tab === "uncertainty & reliability" && (
              <ReliabilityPanel
                payload={payload}
                series={series}
                origin={blk}
                tau={tau}
                onTau={setTau}
              />
            )}
          </div>
        </div>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">models used</h4>
            <p className="wb-evidence-line">
              <code className="wb-tag">routed pipeline</code> — per-series routing on the
              selection origins: ADI ≥ 1.32 (lumpy) series get their best statistical method (
              {Object.entries(payload.catalog_summary.model_used_counts)
                .filter(([m]) => m !== "direct_hgb")
                .map(([m, n]) => (
                  <span key={m}>
                    <code className="wb-tag">{m}</code> ×{n}{" "}
                  </span>
                ))}
              in the catalog); the {payload.catalog_summary.model_used_counts.direct_hgb} erratic
              series stay on the boosted per-horizon HGB. The seasonal-naive floor and the zero
              baseline grade every candidate.
            </p>
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
                {payload.evaluation_metadata.horizons.join("/")} direct horizons
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
              Bands: {(payload.bands.pooled_coverage * 100).toFixed(1)}% pooled coverage (target{" "}
              {(payload.bands.target_coverage * 100).toFixed(0)}%),{" "}
              {payload.bands.pooled_verdict} — {payload.bands.note}
            </p>
            <p className="wb-evidence-line">{payload.decision.label}.</p>
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
              is a set of <strong>direct h-step forecasts</strong>: one model per horizon h on the
              committed lattice, so the <strong>horizon</strong> slider switches between genuinely
              different models and the error genuinely grows with h. The <strong>shock</strong>{" "}
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
              {payload.dataset_metadata.zero_sales_caveat} The erratic class is 15 series — the
              boosted model's edge there is <em>not established</em> (the gap CI spans zero), and
              the order-up-to layer is a simulation with documented costs, not a savings claim:
              on lumpy demand the routed policy costs more than the floor at the committed
              service levels. Inventory planning would still need per-series safety-stock
              calibration and a lead-time objective the experiment does not commit.
            </p>
          </div>
        </>
      }
    />
  );
}

/** Class-verdict notice: what serves this class, and by how much — pooled
 * gap with the bootstrap verdict, plus the honest per-series beats count. */
function ClassVerdictText({ payload, series }: { payload: ForecastPayload; series: CatalogSeries }) {
  const row = scoreboardRow(payload.class_scoreboard, series.demand_class, 7);
  const gap = row.gap;
  const established = gap !== null && !gap.spansZero;
  const pct =
    row.modelMae !== null && row.floorMae !== null && row.floorMae > 0
      ? ((row.floorMae - row.modelMae) / row.floorMae) * 100
      : null;
  if (series.demand_class === "lumpy") {
    return (
      <>
        <strong>Lumpy series</strong> — the boosted model is routed away;{" "}
        <strong>{series.model_used === "direct_hgb" ? "boosted HGB" : series.model_used}</strong>{" "}
        serves this series (committed routing table). At h=7 the routed pipeline beats the
        seasonal-naive floor by{" "}
        <strong>
          {pct !== null ? `${pct.toFixed(0)}%` : "n/a"} pooled ({row.modelMae?.toFixed(2)} vs{" "}
          {row.floorMae?.toFixed(2)} MAE)
        </strong>{" "}
        — {established ? "established" : "not established"} [
        {gap ? `${gap.ci95[0].toFixed(2)}, ${gap.ci95[1].toFixed(2)}` : "n/a"}] — and the zero
        baseline trails by only {row.vsZero ? Math.abs(row.vsZero.diff).toFixed(2) : "n/a"} MAE.
        Per-series honesty: the floor still wins on{" "}
        {row.beatsCount !== null
          ? `${(100 - (row.beatsShare ?? 0) * 100).toFixed(0)}% of ${row.nSeries.toLocaleString()} lumpy series`
          : "n/a"}{" "}
        (pooled ≠ per-series).
      </>
    );
  }
  return (
    <>
      <strong>Erratic series</strong> — one of the {row.nSeries} the boosted per-horizon HGB
      actually serves. At h=7 the gap over the floor is{" "}
      <strong>
        {gap ? `${gap.diff >= 0 ? "+" : ""}${gap.diff.toFixed(2)} MAE` : "n/a"} [
        {gap ? `${gap.ci95[0].toFixed(1)}, ${gap.ci95[1].toFixed(1)}` : "n/a"}]
      </strong>{" "}
      — <strong>not established</strong> with {row.nSeries} series; treat the boosted curve as
      competitive-with-the-floor, not better.
    </>
  );
}

/** Horizon-truth notice: the error-growth ratio derived from the committed
 * growth curves — the h-slider is real. */
function HorizonTruthText({ payload, h }: { payload: ForecastPayload; h: number }) {
  const ratio = growthRatio(payload.horizon_growth, 14, 1);
  return (
    <>
      At <strong>h=14</strong> the pooled error is{" "}
      <strong>~{ratio !== null ? ratio.toFixed(1) : "n/a"}×</strong> the h=1 error (committed
      MASE curves) — the slider is real: each stop is a different direct model, and you are at{" "}
      <strong>h={h}</strong>. The growth curve lives in the reliability tab.
    </>
  );
}
