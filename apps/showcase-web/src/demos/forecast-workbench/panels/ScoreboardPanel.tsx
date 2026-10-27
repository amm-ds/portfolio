import type {
  CatalogSeries,
  DemandClass,
  ForecastPayload,
  ModelKey,
  OriginBlock,
  PeakCandidateStats,
  PeakClassEntry,
} from "../../types";
import { candidateAvailable, fmtDay, horizonKpi, scoreboardRow } from "../kpis";
import { Figure } from "./common";

/** Typed accessor for one candidate's stats inside a class' peak block. */
export function peakStats(entry: PeakClassEntry | undefined, cand: string): PeakCandidateStats | null {
  if (!entry) return null;
  const s = entry[cand as keyof PeakClassEntry];
  return s && typeof s === "object" ? (s as PeakCandidateStats) : null;
}

const CLASSES: DemandClass[] = ["lumpy", "erratic"];
const HS = [7, 14];

/** The model rows offered for ONE series: the universal zero baseline, the
 * committed routed method, the wave-22 ADIDA curve (every series), the
 * boosted direct HGB on erratic series, and the peak-capable candidates only
 * where the router selected them. */
export function seriesModelKeys(series: CatalogSeries): ModelKey[] {
  const keys: ModelKey[] = ["zero", "routed", "adida"];
  if (series.demand_class === "erratic") keys.push("champion");
  if (candidateAvailable(series, "hurdle")) keys.push("hurdle");
  if (candidateAvailable(series, "tweedie")) keys.push("tweedie");
  return keys;
}

/** Why a chip is disabled for this series (the routing tooltip). */
export function modelDisableReason(series: CatalogSeries, m: ModelKey): string | null {
  if (m === "champion" && series.demand_class !== "erratic") {
    return "boosted models don't serve lumpy series — see the routing note";
  }
  if ((m === "hurdle" || m === "tweedie") && !candidateAvailable(series, m)) {
    const short = series.model_used.replace("_hgb", "").replace("hgb_", "");
    return `the router selects ${m} only for the series it won on the training origins — this series routes to ${short}`;
  }
  return null;
}

const ROW_LABEL: Record<string, string> = {
  zero: "zero",
  routed: "routed",
  champion: "boosted HGB",
  hurdle: "hurdle",
  tweedie: "tweedie",
  adida: "adida",
};

/** MODEL SCOREBOARD (always visible): the committed experiment-wide class
 * table, the wave-20 peak-capable candidate rows per class (the routed
 * champion highlighted), and the selected series' per-origin per-model
 * metrics — every table refits on series/origin/h/shock changes, and
 * clicking a row loads that curve in the explorer. */
export function ScoreboardPanel({
  payload,
  series,
  origin,
  model,
  horizon,
  shock,
  onPickModel,
}: {
  payload: ForecastPayload;
  series: CatalogSeries;
  /** The selected origin — its per-origin column is marked. */
  origin: OriginBlock | null;
  model: ModelKey;
  horizon: number;
  shock: number;
  onPickModel: (m: ModelKey) => void;
}) {
  const perOrigin = series.origins.map((o) => ({ date: o.origin_date, blk: o }));
  const rows = seriesModelKeys(series);
  const peak = payload.peak_capture.per_class;

  return (
    <Figure
      comment={
        <>
          Committed per class (pooled, 95% paired bootstrap); candidate rows are the wave-20
          peak-capable methods. The per-origin table is this series — refit live; click a row to
          load its curve.
        </>
      }
    >
      <div className="wb-cmp-wrap wb-cmp-stack">
        <div className="wb-cmp-table-scroll wb-internal-scroll">
        <table className="data-table wb-cmp-table" aria-label="class scoreboard">
          <thead>
            <tr>
              <th>class</th>
              <th>h</th>
              <th>series</th>
              <th>beats floor</th>
              <th>MAE model / floor</th>
              <th>gap [95% CI]</th>
            </tr>
          </thead>
          <tbody>
            {CLASSES.flatMap((cls) =>
              HS.map((h) => {
                const row = scoreboardRow(payload.class_scoreboard, cls, h);
                if (row.modelMae === null) return null;
                const established = row.gap !== null && !row.gap.spansZero;
                return (
                  <tr key={`${cls}-${h}`}>
                    <th>{cls}</th>
                    <td>h={h}</td>
                    <td>{row.nSeries.toLocaleString()}</td>
                    <td>
                      {row.beatsCount !== null
                        ? `${row.beatsCount}/${row.nSeries} (${row.beatsShare !== null ? `${(row.beatsShare * 100).toFixed(0)}%` : "n/a"})`
                        : "n/a"}
                    </td>
                    <td>
                      {row.modelMae.toFixed(2)} / {row.floorMae !== null ? row.floorMae.toFixed(2) : "n/a"}
                    </td>
                    <td>
                      {row.gap ? (
                        <>
                          {row.gap.diff >= 0 ? "+" : ""}
                          {row.gap.diff.toFixed(2)} [{row.gap.ci95[0].toFixed(1)}, {row.gap.ci95[1].toFixed(1)}]{" "}
                          <span className={`chip demo-readout ${established ? "good" : ""}`}>
                            {established ? "established" : "not established"}
                          </span>
                        </>
                      ) : (
                        "n/a"
                      )}
                    </td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>

        <table className="data-table wb-cmp-table" aria-label="peak-capable candidates">
          <thead>
            <tr>
              <th>candidate</th>
              {CLASSES.map((cls) => (
                <th key={cls}>{cls} MAE @h7</th>
              ))}
              {CLASSES.map((cls) => (
                <th key={`pk-${cls}`}>{cls} peak-day</th>
              ))}
              {CLASSES.map((cls) => (
                <th key={`re-${cls}`}>{cls} rmae / rmsse</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["routed", "hurdle", "tweedie"] as const).map((cand) => {
              const method = cand === "routed" ? null : cand === "hurdle" ? "hurdle_hgb" : "hgb_tweedie";
              const mk: ModelKey = cand;
              const disabled = modelDisableReason(series, mk);
              const clsMae = (cls: DemandClass) =>
                method === null
                  ? (payload.class_scoreboard[cls].mae.h7?.model ?? null)
                  : (payload.class_scoreboard[cls].candidates?.[method]?.h7?.mae ?? null);
              const clsPeak = (cls: DemandClass) => peakStats(peak[cls], method ?? "routed")?.peak_mae ?? null;
              const clsRel = (cls: DemandClass) => {
                const entry = method === null ? null : payload.class_scoreboard[cls].candidates?.[method];
                const rmae = entry?.rmae ?? null;
                const rmsse = entry?.rmsse?.rmsse ?? null;
                return rmae !== null && rmsse !== null ? `${rmae.toFixed(3)} / ${rmsse.toFixed(3)}` : "n/a";
              };
              return (
                <tr key={cand} className={`${cand === "routed" ? "wb-cmp-champion" : ""} ${mk === model ? "wb-cmp-active" : ""}`}>
                  <th>
                    <button
                      type="button"
                      className={`wb-model-pick ${mk === model ? "active" : ""}`}
                      aria-pressed={mk === model}
                      disabled={disabled !== null}
                      title={disabled ?? `load the ${ROW_LABEL[cand]} curve`}
                      onClick={() => onPickModel(mk)}
                    >
                      {ROW_LABEL[cand]}
                      {cand === "routed" && <span className="chip demo-readout">champion</span>}
                    </button>
                  </th>
                  {CLASSES.map((cls) => (
                    <td key={cls}>{clsMae(cls) !== null ? clsMae(cls)!.toFixed(2) : "n/a"}</td>
                  ))}
                  {CLASSES.map((cls) => (
                    <td key={`pk-${cls}`}>{clsPeak(cls) !== null ? clsPeak(cls)!.toFixed(1) : "n/a"}</td>
                  ))}
                  {CLASSES.map((cls) => (
                    <td key={`re-${cls}`}>{clsRel(cls)}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>

        <table className="data-table wb-cmp-table" aria-label="per-origin model metrics">
          <thead>
            <tr>
              <th>model</th>
              {perOrigin.map((o) => (
                <th key={o.date} className={o.date === origin?.origin_date ? "wb-cmp-col-active" : ""}>
                  {fmtDay(o.date)}
                  {o.date === origin?.origin_date ? " ◀" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((mk) => {
              const disabled = modelDisableReason(series, mk);
              return (
                <tr key={mk} className={mk === model ? "wb-cmp-active" : ""}>
                  <th>
                    <button
                      type="button"
                      className={`wb-model-pick ${mk === model ? "active" : ""}`}
                      aria-pressed={mk === model}
                      disabled={disabled !== null}
                      title={disabled ?? `load the ${ROW_LABEL[mk]} curve`}
                      onClick={() => onPickModel(mk)}
                    >
                      {ROW_LABEL[mk]}
                    </button>
                  </th>
                  {perOrigin.map(({ date, blk }) => {
                    const k = horizonKpi(blk, mk, shock, horizon);
                    return (
                      <td key={date}>
                        {k ? (
                          <>
                            <span className="wb-cmp-cell">MAE {k.mae.toFixed(2)}</span>
                            <span className="wb-cmp-cell">MASE {k.mase !== null ? k.mase.toFixed(2) : "n/a"}</span>
                          </>
                        ) : (
                          "n/a"
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </div>
    </Figure>
  );
}
