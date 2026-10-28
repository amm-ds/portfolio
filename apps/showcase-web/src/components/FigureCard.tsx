import { useState } from "react";
import { PlotlyFigure, type PlotlyPayload } from "./PlotlyFigure";

type AnyRecord = Record<string, unknown>;

function asRecord(v: unknown): AnyRecord {
  return typeof v === "object" && v !== null ? (v as AnyRecord) : {};
}

/** Axis title text: plotly allows `{title: {text}}` or the shorthand `{title: "..."}`. */
function axisTitle(axis: unknown): string | null {
  const t = asRecord(axis).title;
  if (typeof t === "string" && t) return t;
  const text = asRecord(t).text;
  return typeof text === "string" && text ? text : null;
}

/** Compact number formatting for the table cells. */
function fmt(v: number): string {
  if (Number.isInteger(v) && Math.abs(v) < 1e9) return v.toLocaleString("en-US");
  return v.toPrecision(3);
}

interface TraceSummary {
  name: string;
  first: string | null;
  last: string | null;
  points: number;
}

/**
 * One row per trace: the series name plus its first/last values and point
 * count. Traces without a numeric y array (pie, table, …) degrade to a
 * point-count row so the fallback stays compact for any figure type.
 */
function summarizeTraces(data: unknown[]): TraceSummary[] {
  return data.map((raw, i) => {
    const t = asRecord(raw);
    const name = typeof t.name === "string" && t.name !== "" ? t.name : `trace ${i + 1}`;
    const y = Array.isArray(t.y) ? t.y : null;
    if (y !== null && y.length > 0) {
      const nums = y.filter(
        (v): v is number => typeof v === "number" && Number.isFinite(v),
      );
      return {
        name,
        first: nums.length > 0 ? fmt(nums[0]) : null,
        last: nums.length > 0 ? fmt(nums[nums.length - 1]) : null,
        points: y.length,
      };
    }
    const xLen = Array.isArray(t.x) ? t.x.length : null;
    return { name, first: null, last: null, points: xLen ?? 1 };
  });
}

type DataStatus = { state: "loading" } | { state: "ok"; payload: PlotlyPayload } | { state: "unavailable" };

/**
 * Generic figure card: one bordered tile holding a chart (native plotly,
 * iframe fallback inside PlotlyFigure) on top and a commentary band at the
 * bottom — a small mono id line (`fig :: {name}`) plus an optional caption
 * paragraph from the story's `figure_captions`. Usable by any page/project;
 * when no caption exists yet the band falls back to the id line alone.
 *
 * The band ends with a collapsed `view data table` disclosure — a compact
 * per-series table parsed from the same plotly JSON payload, as a
 * non-visual fallback for the chart.
 */
export function FigureCard({
  pid,
  name,
  caption,
}: {
  pid: string;
  name: string;
  caption?: string;
}) {
  const [data, setData] = useState<DataStatus>({ state: "loading" });
  const rows = data.state === "ok" ? summarizeTraces(data.payload.data) : [];
  const xTitle = data.state === "ok" ? axisTitle(asRecord(data.payload.layout).xaxis) : null;
  const yTitle = data.state === "ok" ? axisTitle(asRecord(data.payload.layout).yaxis) : null;

  return (
    <div className="figure-card">
      <PlotlyFigure pid={pid} name={name} onPayload={(p) => setData(p ? { state: "ok", payload: p } : { state: "unavailable" })} />
      <footer className="figure-card-band">
        <span className="figure-id">fig :: {name}</span>
        {caption && <p className="figure-comment">{caption}</p>}
        <details className="figure-data">
          <summary>view data table</summary>
          {data.state === "ok" && rows.length > 0 ? (
            <table className="data-table">
              {(xTitle !== null || yTitle !== null) && (
                <caption>
                  {xTitle !== null && <>x: {xTitle}</>}
                  {xTitle !== null && yTitle !== null && " · "}
                  {yTitle !== null && <>y: {yTitle}</>}
                </caption>
              )}
              <thead>
                <tr>
                  <th scope="col">series</th>
                  <th scope="col">first</th>
                  <th scope="col">last</th>
                  <th scope="col">points</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.name}-${i}`}>
                    <th scope="row">{r.name}</th>
                    <td>{r.first ?? "—"}</td>
                    <td>{r.last ?? "—"}</td>
                    <td>{r.points.toLocaleString("en-US")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="figure-data-note">
              {data.state === "loading" ? "loading figure data…" : "data table unavailable for this figure"}
            </p>
          )}
        </details>
      </footer>
    </div>
  );
}
