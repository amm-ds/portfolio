import { useEffect, useState, type ReactNode } from "react";
import { LineChart } from "../charts/LineChart";
import type { CatalogEntry, DemoManifest, ForecastWorkbenchPayload } from "../types";
import { DemoFigure, DemoWorkbench, KpiTile, Notice, useControlState } from "../workbench";
import { C_AMBER, C_HIST, C_PINK, MODELS, MODEL_LABELS, assembleChartData } from "./chartData";
import { bestModelAt, verdictText, wapeAt } from "./kpis";
import { ErrorCompositionPanel, ModelSpreadPanel, VerdictPanel } from "./panels";
import { fetchForecastPayload } from "./payload";
import { getDemoManifest } from "../../api";
import { usePageMeta } from "../../seo";

const HORIZONS = [7, 14, 21, 28];
const NAIVE = "seasonal_naive";

/** Default overlay: the seasonal-naive floor against the champion screened
 *  ensemble — the two curves that carry the story. Every other candidate
 *  stays one chip away. */
const DEFAULT_MODELS = "seasonal_naive,convex_ensemble";

/** Minimal manifest so the workbench renders before/if the manifest fetch fails.
 * Mirrors projects/02-demand-forecasting/demo.yaml — keep hook/hero/scenarios
 * in sync (the payload itself is pinned by the contract tests). */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "Demand Forecast Workbench",
  hook: "Pick one of 48 committed M5 store-product series, overlay all 8 candidates from the seasonal naive to the screened ensemble on the scored-once competition window — curves, model spread and per-series WAPE respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser"],
  hero: {
    label: "official WRMSSE",
    value: "0.6161 vs 0.8929",
    ci: "−31.0% on the competition window (m5_full_v1, horizon 28)",
  },
  scenarios: [
    { name: "base", controls: { models: "seasonal_naive,lgbm", horizon: 28 } },
    {
      name: "full-horizon-ensemble",
      controls: {
        models: "seasonal_naive,auto_ets,lgbm,lgbm_tweedie,lgbm_pool_store,lgbm_pool_storecat,lgbm_pool_dept,convex_ensemble",
        horizon: 28,
      },
    },
    {
      name: "pooled-compare",
      controls: {
        models: "seasonal_naive,lgbm,lgbm_pool_store,lgbm_pool_storecat,lgbm_pool_dept,convex_ensemble",
        horizon: 28,
      },
    },
    { name: "short-window", controls: { models: "seasonal_naive,convex_ensemble", horizon: 7 } },
  ],
  live_endpoints: [],
  payload: {
    path: "reports_m5_full/demo_payload.json",
    schema_version: 4,
    required_keys: ["demo", "project", "protocol", "catalog", "groups", "origins", "evaluation_metadata"],
  },
};

/** Short display name: strip the trailing `_<STORE>` token from the id. */
function shortId(sid: string): string {
  const parts = sid.split("_");
  return parts.slice(0, -1).join("_") || sid;
}

/** Category token of a series id (`FOODS_3_090_CA_1` → `FOODS`). */
function catOf(sid: string): string {
  return sid.split("_")[0] ?? sid;
}

/** A row of selectable chips (models / horizon share the shape). */
function ChipRow({
  options,
  active,
  onPick,
}: {
  options: { key: string; label: ReactNode; tooltip?: string }[];
  active: (key: string) => boolean;
  onPick: (key: string) => void;
}) {
  return (
    <div className="demo-presets">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          className={`chip demo-preset ${active(o.key) ? "fwb-active" : ""}`}
          aria-pressed={active(o.key)}
          title={o.tooltip}
          onClick={() => onPick(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function ForecastWorkbench() {
  usePageMeta({
    title: "Demand forecast workbench",
    description:
      "Interactive full-panel M5 demand-forecasting demo: compare the seasonal naive, AutoETS, global and pooled LightGBM arms and the screened ensemble on the scored-once competition window.",
  });

  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<ForecastWorkbenchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoManifest("forecast-workbench")
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

function Workbench({
  manifest,
  payload,
}: {
  manifest: DemoManifest;
  payload: ForecastWorkbenchPayload;
}) {
  const firstSeries = payload.catalog[0]?.series_id ?? "";
  // single scored-once origin by design: no origin control
  const state = useControlState<string | number>(
    { series: firstSeries, models: DEFAULT_MODELS, horizon: 28 },
    manifest.scenarios,
  );
  const { controls: values, setControl: setValue } = state;

  const seriesId = payload.catalog.some((e) => e.series_id === values.series)
    ? String(values.series)
    : firstSeries;
  const h = HORIZONS.includes(Number(values.horizon)) ? Number(values.horizon) : 28;
  const modelsOn = String(values.models)
    .split(",")
    .filter((m) => MODELS.some((mm) => mm.key === m));

  const entry = payload.catalog.find((e) => e.series_id === seriesId) ?? payload.catalog[0];
  const window = entry.windows;
  const originBlock = payload.origins[0];

  const cycle = (delta: number) => {
    const idx = payload.catalog.findIndex((e) => e.series_id === entry.series_id);
    const next = payload.catalog[(idx + delta + payload.catalog.length) % payload.catalog.length];
    setValue("series", next.series_id);
  };
  const surprise = () => {
    const others = payload.catalog.filter((e) => e.series_id !== entry.series_id);
    if (others.length > 0) {
      setValue("series", others[Math.floor(Math.random() * others.length)].series_id);
    }
  };
  const toggleModel = (key: string) => {
    const next = modelsOn.includes(key)
      ? modelsOn.filter((m) => m !== key)
      : [...modelsOn, key];
    if (next.length > 0) setValue("models", next.join(","));
  };

  const best = bestModelAt(window, modelsOn, h);
  const modelWape = best ? wapeAt(window.actual, window.curves[best], h) : 0;
  const naiveWape = wapeAt(window.actual, window.curves[NAIVE], h);
  const pooled = payload.groups.test_pooled;
  // committed pooled gap, quoted only at the full scored horizon
  const committedGap =
    h === 28 && best && pooled[best] && pooled[NAIVE] ? pooled[best].wrmsse - pooled[NAIVE].wrmsse : null;
  const band = payload.groups.band.candidates.convex_ensemble;
  const ensemblePooled = pooled.convex_ensemble;
  const naivePooled = pooled[NAIVE];
  const relGap = payload.groups.headline.convex_ensemble_vs_naive.wrmsse.rel;
  const signed = (value: number) =>
    `${value < 0 ? "−" : value > 0 ? "+" : ""}${Math.abs(value).toFixed(1)}`;
  const winRate = payload.groups.win_rate_vs_naive.convex_ensemble;
  const classCounts = payload.groups.classes.counts;
  const candidateCount = Object.keys(pooled).length;
  const stores = [...new Set(payload.catalog.map((e) => e.store))].sort();

  return (
    <DemoWorkbench
      manifest={manifest}
      state={state}
      controls={
        <>
          <div className="wb-control-group wb-group-series">
            <span className="wb-rail-title">Series</span>
            <div className="demo-control">
              <div className="demo-readouts">
                <button type="button" className="chip demo-readout" onClick={() => cycle(-1)}>
                  ‹ prev
                </button>
                <button type="button" className="chip demo-readout" onClick={() => cycle(1)}>
                  next ›
                </button>
                <button type="button" className="chip demo-readout" onClick={surprise}>
                  surprise me
                </button>
              </div>
              <div className="fwb-store-scroll">
                {stores.map((store) => (
                  <div key={store} className="fwb-store">
                    <span className="fwb-store-tag">{store}</span>
                    {(["top_units", "bottom_intermittency"] as const).map((half) => {
                      const rows = payload.catalog.filter(
                        (e) => e.store === store && e.half === half,
                      );
                      if (rows.length === 0) return null;
                      return (
                        <div key={half} className="fwb-store">
                          <span className="fwb-store-tag">
                            {half === "top_units" ? "top units" : "hardest intermittent"}
                          </span>
                          <div className="demo-presets">
                            {rows.map((e) => (
                              <button
                                key={e.series_id}
                                type="button"
                                className={`chip demo-preset ${e.series_id === entry.series_id ? "fwb-active" : ""}`}
                                aria-pressed={e.series_id === entry.series_id}
                                title={`${catOf(e.series_id)} · ${e.units_last_28d.toFixed(0)} units in the scored window · ADI ${e.adi.toFixed(2)}, CV² ${e.cv2.toFixed(2)}`}
                                onClick={() => setValue("series", e.series_id)}
                              >
                                {shortId(e.series_id)}
                                <span className={`fwb-badge fwb-badge-${e.class}`}>{e.class}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="wb-control-group wb-group-models">
            <span className="wb-rail-title">Models</span>
            <div className="demo-control">
              <ChipRow
                options={MODELS.map((m) => ({
                  key: m.key,
                  label: (
                    <>
                      <span className="fwb-dot" style={{ background: m.color }} />
                      {m.label}
                    </>
                  ),
                  tooltip: m.tooltip,
                }))}
                active={(k) => modelsOn.includes(k)}
                onPick={toggleModel}
              />
            </div>
          </div>
          <div className="wb-control-group wb-group-horizon">
            <span className="wb-rail-title">Horizon</span>
            <div className="demo-control">
              <ChipRow
                options={HORIZONS.map((hh) => ({ key: String(hh), label: `${hh}d` }))}
                active={(k) => Number(k) === h}
                onPick={(k) => setValue("horizon", Number(k))}
              />
            </div>
          </div>
        </>
      }
      canvas={
        <ForecastChart
          entry={entry}
          window={window}
          origin={originBlock.origin}
          modelsOn={modelsOn}
          h={h}
        />
      }
      kpis={
        <>
          <KpiTile
            label={`WAPE @ ${h}d`}
            value={`${(modelWape * 100).toFixed(1)}%`}
            sub={`${best ? MODEL_LABELS[best] : "—"} vs naive ${(naiveWape * 100).toFixed(1)}%${
              committedGap !== null
                ? ` · pooled WRMSSE ${committedGap > 0 ? "+" : "−"}${Math.abs(committedGap).toFixed(4)} committed`
                : ""
            }`}
            tone={modelWape < naiveWape ? "good" : modelWape > naiveWape ? "bad" : "neutral"}
          />
          <KpiTile
            label="official WRMSSE"
            value={`${ensemblePooled.wrmsse.toFixed(4)}`}
            sub={`champion ensemble vs floor ${naivePooled.wrmsse.toFixed(4)} (${(relGap * 100).toFixed(1)}%) · 42,840 nodes, scored once`}
            tone="good"
          />
          <KpiTile
            label="zero-day accuracy"
            value={`${(ensemblePooled.zero_day_accuracy * 100).toFixed(1)}%`}
            sub={`ensemble vs floor ${(naivePooled.zero_day_accuracy * 100).toFixed(1)}% · committed, all 30,490 series`}
            tone={ensemblePooled.zero_day_accuracy < naivePooled.zero_day_accuracy ? "bad" : "good"}
          />
        </>
      }
      notice={<Notice>{verdictText(window, best, h)}</Notice>}
      secondary={
        <>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">error composition</h3>
            <ErrorCompositionPanel window={window} primary={best} h={h} />
          </div>
          <div className="wb-secondary-panel">
            <h3 className="wb-rail-title">model spread</h3>
            <ModelSpreadPanel
              window={window}
              modelsOn={modelsOn}
              h={h}
              forecastDates={originBlock.forecast_dates}
            />
          </div>
          <div className="wb-secondary-panel wb-secondary-panel--wide">
            <h3 className="wb-rail-title">model verdict</h3>
            <VerdictPanel
              entry={entry}
              window={window}
              modelsOn={modelsOn}
              h={h}
              payload={payload}
            />
          </div>
        </>
      }
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              Per-series forecast curves from the committed full-panel M5 track
              (protocol <code className="wb-tag">{payload.protocol}</code>) for
              a deterministic {payload.catalog.length}-series catalog, all
              scored once on the competition window ({originBlock.origin} →{" "}
              {originBlock.forecast_dates[originBlock.forecast_dates.length - 1]}). The headline is
              the pooled official WRMSSE: ensemble {ensemblePooled.wrmsse.toFixed(4)} vs the
              seasonal-naive floor {naivePooled.wrmsse.toFixed(4)} (gap{" "}
              {signed(relGap * 100)}%).
            </p>
            {entry.class === "intermittent" ? (
              <p className="wb-evidence-line" data-testid="honest-gap">
                The honest gap: this is an intermittent series (ADI {entry.adi.toFixed(2)}) — the
                floor can still win it
                {winRate.intermittent !== null &&
                  ` (across the catalog the ensemble wins ${(winRate.intermittent * 100).toFixed(1)}% of intermittent series; `}
                the member envelope is a min/max band, not a calibrated interval
                {winRate.intermittent !== null ? ")" : ""}. Per-series WAPEs here are computed
                from the committed payload curves — a catalog statistic, never a panel claim.
              </p>
            ) : (
              <p className="wb-evidence-line">
                On dense series the candidates trade the weekly shape against event days.
                Per-series WAPEs here are computed from the committed payload curves — a catalog
                statistic, never a panel claim.
              </p>
            )}
            <p className="wb-evidence-line">
              <a href="/projects/02-demand-forecasting">Read the project report</a>{" "}
              for the full track — {classCounts.dense.toLocaleString("en-US")} dense +{" "}
              {classCounts.intermittent.toLocaleString("en-US")} intermittent series,{" "}
              {candidateCount} candidates, the official 42,840-node hierarchical WRMSSE.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">committed numbers</h4>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">
                catalog win rate {(winRate.pooled * 100).toFixed(1)}%
              </span>
              <span className="wb-tag">
                bottom WAPE {ensemblePooled.wape.toFixed(3)} vs {naivePooled.wape.toFixed(3)}
              </span>
              <span className="wb-tag">
                envelope {band.mean_width.toFixed(1)}u mean width (catalog)
              </span>
              <span className="wb-tag">
                half {entry.half === "top_units" ? "top-units" : "hardest intermittent"}
              </span>
            </p>
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The demo isolates one store-product series at the single
              scored-once origin: the 56-day history tail, the 28-day actuals,
              and each candidate's curve. The <strong>horizon</strong> toggle
              shortens the scored window client-side; the <strong>models</strong>{" "}
              chips overlay the 8 committed candidates; the ensemble adds its
              member envelope (per-day min/max of the blend members — an
              envelope, not a calibrated interval).
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              Walmart M5 accuracy competition, full panel (30,490 series), 3
              weekly rolling origins — the last scored once. Nothing read the
              test origin at fit time; the ensemble members and weights were
              chosen on the 2 selection origins only. Curves are copied from
              the committed catalog run — no re-fitting in the browser.
            </p>
          </div>
        </>
      }
    />
  );
}

/** The single chart: history tail + 28-day actuals + selected model curves +
 * the ensemble member envelope, on a clipped domain so short horizons never
 * render flat. */
function ForecastChart({
  entry,
  window,
  origin,
  modelsOn,
  h,
}: {
  entry: CatalogEntry;
  window: CatalogEntry["windows"];
  origin: string;
  modelsOn: string[];
  h: number;
}) {
  const { x, series, band, yMax, take } = assembleChartData(window, modelsOn, h);

  const legend = [
    { label: "history", color: C_HIST },
    { label: "actual", color: C_PINK },
    ...MODELS.filter((m) => modelsOn.includes(m.key)).map((m) => ({ label: m.label, color: m.color })),
    ...(band ? [{ label: "ensemble envelope", color: C_AMBER }] : []),
  ];

  return (
    <DemoFigure
      comment={
        <>
          {entry.series_id} ({entry.class}, {entry.units_last_28d.toFixed(0)} units/28d) from origin{" "}
          {origin} — history tail, 28-day actuals and the selected candidates; the domain clips to
          the visible window.
        </>
      }
    >
      <div className="demo-readouts">
        {legend.map((l) => (
          <span key={l.label} className="chip demo-readout">
            <span className="fwb-dot" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
      <div className="demo-chart">
        <LineChart
          x={x}
          series={series}
          yMax={yMax}
          band={band ? { between: band, color: C_AMBER, opacity: 0.12 } : undefined}
          yTicks={3}
          xTicks={4}
          formatX={(v) => {
            // tick slots are fractional positions across the day domain —
            // label the nearest day so the axis never prints long decimals
            const d = Math.round(v);
            return d <= 0 ? `d${d}` : `+${d}`;
          }}
          ariaLabel="forecast curves versus actuals for the selected series"
        />
      </div>
      <p className="demo-hint">history tail ends at the origin; +1…+{take} is the scored window</p>
    </DemoFigure>
  );
}
