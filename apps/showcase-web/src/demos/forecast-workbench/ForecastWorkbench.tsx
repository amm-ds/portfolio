import { useEffect, useState, type ReactNode } from "react";
import { LineChart } from "../charts/LineChart";
import type { CatalogEntry, DemoManifest, ForecastWorkbenchPayload } from "../types";
import { DemoWorkbench, KpiTile, Notice } from "../workbench";
import { C_HIST, C_PINK, C_TEAL, MODELS, assembleChartData } from "./chartData";
import { bestModelAt, peakDayMae, verdictText, wapeAt } from "./kpis";
import { fetchForecastPayload, fetchManifest } from "./payload";
import { useWorkbenchState } from "./useWorkbenchState";

const HORIZONS = [7, 14, 21, 28];
const NAIVE = "seasonal_naive";

const MODEL_LABELS = Object.fromEntries(MODELS.map((m) => [m.key, m.label]));

/** Minimal manifest so the workbench renders before/if the manifest fetch fails. */
const FALLBACK_MANIFEST: DemoManifest = {
  id: "forecast-workbench",
  title: "demand forecast workbench",
  hook: "Pick a store-product series from the committed M5 track, compare the seasonal naive, AutoETS, LightGBM and the pooled ensemble on the two scored-once test origins, and slide the horizon — watch the curves, the 80% band and the per-series WAPE respond.",
  project: "02-demand-forecasting",
  group: "plan operations",
  skills: ["time series forecasting", "prediction intervals", "demand classification"],
  modes: ["browser"],
  hero: {
    label: "pooled test WAPE, ensemble vs seasonal-naive floor (600 series, 2 scored origins)",
    value: "0.498 vs 0.603",
    ci: "paired bootstrap CI [−0.115, −0.095] on the −0.105 gap; 89.3% per-series win rate; 80% band covers 78.7% (protocol m5_direct_v1, horizon 28)",
  },
  scenarios: [
    { name: "base", controls: { models: "seasonal_naive,lgbm", origin: "2016-05-10", horizon: 28 } },
    {
      name: "full-horizon-ensemble",
      controls: { models: "seasonal_naive,auto_ets,lgbm,convex_ensemble", origin: "2016-05-17", horizon: 28 },
    },
    { name: "short-window", controls: { models: "seasonal_naive,convex_ensemble", origin: "2016-05-10", horizon: 7 } },
  ],
  live_endpoints: [],
  payload: { path: "reports_m5/demo_payload.json", schema_version: 4, required_keys: [] },
};

/** Short display name: strip the trailing `_<STORE>` token from the id. */
function shortId(sid: string): string {
  const parts = sid.split("_");
  return parts.slice(0, -1).join("_") || sid;
}

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

/** A row of selectable chips (models / origin / horizon share the shape). */
function ChipRow({
  options,
  active,
  onPick,
}: {
  options: { key: string; label: ReactNode }[];
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
          onClick={() => onPick(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function ForecastWorkbench() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [payload, setPayload] = useState<ForecastWorkbenchPayload | null>(null);
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

function Workbench({
  manifest,
  payload,
}: {
  manifest: DemoManifest;
  payload: ForecastWorkbenchPayload;
}) {
  const firstSeries = payload.catalog[0]?.series_id ?? "";
  const firstOrigin = payload.origins[0]?.origin ?? "";
  const state = useWorkbenchState(
    { series: firstSeries, models: "seasonal_naive,lgbm", origin: firstOrigin, horizon: 28 },
    manifest.scenarios,
  );
  const { values, setValue } = state;

  const seriesId = payload.catalog.some((e) => e.series_id === values.series)
    ? String(values.series)
    : firstSeries;
  const origin = payload.origins.some((o) => o.origin === values.origin)
    ? String(values.origin)
    : firstOrigin;
  const h = HORIZONS.includes(Number(values.horizon)) ? Number(values.horizon) : 28;
  const modelsOn = String(values.models)
    .split(",")
    .filter((m) => MODELS.some((mm) => mm.key === m));

  const entry = payload.catalog.find((e) => e.series_id === seriesId) ?? payload.catalog[0];
  const window = entry.origins[origin];
  const originBlock = payload.origins.find((o) => o.origin === origin)!;

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
  const modelPeak = best ? peakDayMae(window.actual, window.curves[best], h) : 0;
  const naivePeak = peakDayMae(window.actual, window.curves[NAIVE], h);
  // committed pooled gap, quoted only at the full scored horizon
  const pooled = payload.groups.test_pooled;
  const committedGap =
    h === 28 && best && pooled[best] && pooled[NAIVE] ? pooled[best].wape - pooled[NAIVE].wape : null;
  const band = payload.groups.band.candidates.lgbm;

  const stores = [...new Set(payload.catalog.map((e) => e.store))].sort();

  return (
    <DemoWorkbench
      manifest={manifest}
      state={{
        controls: Object.fromEntries(Object.entries(values).map(([k, v]) => [k, Number(v)])),
        setControl: (key, value) => {
          const raw = values[key];
          setValue(key, typeof raw === "number" ? value : String(value));
        },
        activeScenario: state.activeScenario,
        applyScenario: state.applyScenario,
        reset: () => {
          state.reset();
          setValue("series", firstSeries);
        },
        shareUrl: "",
      }}
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
              {stores.map((store) => (
                <div key={store} className="fwb-store">
                  <span className="fwb-store-tag">{store}</span>
                  <div className="demo-presets">
                    {payload.catalog
                      .filter((e) => e.store === store)
                      .map((e) => (
                        <button
                          key={e.series_id}
                          type="button"
                          className={`chip demo-preset ${e.series_id === entry.series_id ? "fwb-active" : ""}`}
                          onClick={() => setValue("series", e.series_id)}
                        >
                          {shortId(e.series_id)}
                          <span className={`fwb-badge fwb-badge-${e.class}`}>{e.class}</span>
                        </button>
                      ))}
                  </div>
                </div>
              ))}
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
                }))}
                active={(k) => modelsOn.includes(k)}
                onPick={toggleModel}
              />
            </div>
          </div>
          <div className="wb-control-group wb-group-origin">
            <span className="wb-rail-title">Origin</span>
            <div className="demo-control">
              <ChipRow
                options={payload.origins.map((o) => ({ key: o.origin, label: o.origin }))}
                active={(k) => k === origin}
                onPick={(k) => setValue("origin", k)}
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
          historyStart={originBlock.history_start}
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
                ? ` · pooled ${committedGap > 0 ? "+" : "−"}${(Math.abs(committedGap) * 100).toFixed(1)} pts committed`
                : ""
            }`}
            tone={modelWape < naiveWape ? "good" : modelWape > naiveWape ? "bad" : "neutral"}
          />
          <KpiTile
            label="band coverage"
            value={`${(band.coverage_80 * 100).toFixed(1)}%`}
            sub={`committed, all 600 series · target 80% · mean width ${band.mean_band_width.toFixed(1)} units`}
          />
          <KpiTile
            label={`peak-day MAE @ ${h}d`}
            value={best ? modelPeak.toFixed(1) : "—"}
            sub={`naive ${naivePeak.toFixed(1)} units · top-decile days`}
            tone={modelPeak < naivePeak ? "good" : modelPeak > naivePeak ? "bad" : "neutral"}
          />
        </>
      }
      notice={<Notice>{verdictText(window, best, h)}</Notice>}
      evidence={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              Per-series forecast curves recomputed by the committed M5 track
              (protocol <code className="wb-tag">m5_direct_v1</code>) for a
              balanced 24-series catalog, scored on the two test origins{" "}
              {payload.origins.map((o) => o.origin).join(" and ")}. The headline
              is the pooled gap: ensemble WAPE 0.498 vs the seasonal-naive
              floor 0.603 (95% CI [−0.115, −0.095]).
            </p>
            {entry.class === "intermittent" ? (
              <p className="wb-evidence-line" data-testid="honest-gap">
                The honest gap: this is an intermittent series — the band runs
                wide and the seasonal naive can still win individual windows
                (the ensemble wins 90.5% of intermittent series; the 80% band
                covers 78.7% of actuals, just under target). Per-series WAPEs
                here are computed from the payload curves; the LightGBM curve
                is a documented catalog-subset refit.
              </p>
            ) : (
              <p className="wb-evidence-line">
                On dense series the candidates trade the weekly shape against
                event days. Per-series WAPEs here are computed from the payload
                curves; the LightGBM curve is a documented catalog-subset refit.
              </p>
            )}
            <p className="wb-evidence-line">
              <a href="/projects/02-demand-forecasting">Read the project report</a>{" "}
              for the full track — 463 dense + 137 intermittent series, 8
              candidates, WRMSSE with the documented naive-28 denominator.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">committed numbers</h4>
            <p className="wb-evidence-line wb-metric-tags">
              <span className="wb-tag">
                ensemble win rate {(payload.groups.win_rate_vs_naive.convex_ensemble.pooled * 100).toFixed(1)}%
              </span>
              <span className="wb-tag">WRMSSE 0.604 vs 0.762</span>
              <span className="wb-tag">
                band {(band.coverage_80 * 100).toFixed(1)}% @ {(band.mean_band_width).toFixed(1)}u
              </span>
              <span className="wb-tag">shape {window.shape}</span>
            </p>
          </div>
        </>
      }
      about={
        <>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">what this shows</h4>
            <p className="wb-evidence-line">
              The demo isolates one store-product series at one scored origin:
              the 56-day history tail, the 28-day actuals, and each candidate's
              curve. The <strong>horizon</strong> toggle shortens the scored
              window client-side; the <strong>models</strong> chips overlay
              candidates; the LightGBM selection adds its conformal band.
            </p>
          </div>
          <div className="wb-result-block">
            <h4 className="wb-evidence-tag">the experiment</h4>
            <p className="wb-evidence-line">
              Walmart M5 accuracy subset (600 series), 10 weekly rolling
              origins — the last 2 scored once. Nothing read the test origins
              at fit time; the ensemble weight and the band widths were
              calibrated on the 8 selection origins only.
            </p>
          </div>
        </>
      }
    />
  );
}

/** The single chart: history tail + 28-day actuals + selected model curves +
 * the lgbm band, on a clipped domain so short horizons never render flat. */
function ForecastChart({
  entry,
  window,
  historyStart,
  modelsOn,
  h,
}: {
  entry: CatalogEntry;
  window: CatalogEntry["origins"][string];
  historyStart: string;
  modelsOn: string[];
  h: number;
}) {
  const { x, series, band, yMax, take } = assembleChartData(window, modelsOn, h);

  const legend = [
    { label: "history", color: C_HIST },
    { label: "actual", color: C_PINK },
    ...MODELS.filter((m) => modelsOn.includes(m.key)).map((m) => ({ label: m.label, color: m.color })),
    ...(band ? [{ label: "lgbm 80% band", color: C_TEAL }] : []),
  ];

  return (
    <Figure
      comment={
        <>
          {entry.series_id} ({entry.class}, {window.shape}) from origin {historyStart} — history
          tail, 28-day actuals and the selected candidates; the domain clips to the visible window.
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
          band={band ? { between: band, color: C_TEAL, opacity: 0.12 } : undefined}
          yTicks={3}
          xTicks={4}
          formatX={(v) => (v <= 0 ? `d${v}` : `+${v}`)}
          ariaLabel="forecast curves versus actuals for the selected series"
        />
      </div>
      <p className="demo-hint">history tail ends at the origin; +1…+{take} is the scored window</p>
    </Figure>
  );
}
