/* eslint-disable jsx-a11y/no-noninteractive-tabindex -- Focusable table regions allow keyboard scrolling. */
import { useState } from "react";
import { asRecord } from "../lib/records";
import { EChartsFigure } from "./EChartsFigure";
import type { PlotlyPayload } from "./PlotlyFigure";

const MAX_TABLE_ROWS = 200;

type Cell = string | number | null;
type FigureRow = Record<string, Cell | undefined> & { series: string };

interface FigureData {
  columns: string[];
  rows: FigureRow[];
  total: number;
  /** Display labels for dynamic table columns, keyed by the column id. */
  labels?: Record<string, string>;
}

const COLUMN_LABELS: Record<string, string> = {
  series: "series",
  x: "x",
  y: "y",
  sample: "sample",
  stage: "stage",
  location: "location",
  longitude: "longitude",
  latitude: "latitude",
  label: "label",
  value: "value",
};
const COLUMN_ORDER = Object.keys(COLUMN_LABELS);

function columnLabel(data: FigureData, column: string): string {
  return data.labels?.[column] ?? COLUMN_LABELS[column] ?? column;
}

/** Axis title text: plotly allows `{title: {text}}` or the shorthand `{title: "..."}`. */
function axisTitle(axis: unknown): string | null {
  const t = asRecord(axis).title;
  if (typeof t === "string" && t) return t;
  const text = asRecord(t).text;
  return typeof text === "string" && text ? text : null;
}

function cell(value: unknown): Cell {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return String(value);
  return null;
}

const BDATA_ARRAYS: Record<string, (buffer: ArrayBuffer) => ArrayLike<number>> = {
  f8: (buffer) => new Float64Array(buffer),
  f4: (buffer) => new Float32Array(buffer),
  i4: (buffer) => new Int32Array(buffer),
  u4: (buffer) => new Uint32Array(buffer),
  i2: (buffer) => new Int16Array(buffer),
  u2: (buffer) => new Uint16Array(buffer),
  i1: (buffer) => new Int8Array(buffer),
  u1: (buffer) => new Uint8Array(buffer),
};

/** Decode plotly's little-endian typed-array JSON representation. */
function values(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  const record = asRecord(value);
  const make = BDATA_ARRAYS[String(record.dtype)];
  if (!make || typeof record.bdata !== "string") return [];
  try {
    const bytes = Uint8Array.from(atob(record.bdata), (character) => character.charCodeAt(0));
    const buffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(buffer).set(bytes);
    const decoded = make(buffer);
    return Array.from({ length: decoded.length }, (_, index) => Number(decoded[index]));
  } catch {
    return [];
  }
}

function heatmapGrid(trace: Record<string, unknown>): unknown[][] {
  if (Array.isArray(trace.z)) {
    return trace.z.every(Array.isArray) ? (trace.z as unknown[][]) : [];
  }
  const encoded = asRecord(trace.z);
  const shape =
    typeof encoded.shape === "string"
      ? encoded.shape.split(",").map((part) => Number(part.trim()))
      : values(encoded.shape);
  const flat = values(encoded);
  if (
    shape.length !== 2 ||
    typeof shape[0] !== "number" ||
    typeof shape[1] !== "number" ||
    flat.length !== shape[0] * shape[1]
  ) {
    return [];
  }
  const [rowCount, columnCount] = shape;
  return Array.from({ length: rowCount }, (_, row) =>
    flat.slice(row * columnCount, (row + 1) * columnCount),
  );
}

/**
 * Flatten plotted values, not trace summaries, into rows shared by the table
 * and CSV download. Only the table is bounded; the complete CSV is constructed
 * on demand so large figures never create an equally large DOM.
 */
function figureData(payload: PlotlyPayload, limit = Number.MAX_SAFE_INTEGER): FigureData {
  const rows: FigureRow[] = [];
  let total = 0;
  let dynamicLabels: Record<string, string> | undefined;
  const add = (row: FigureRow) => {
    total += 1;
    if (rows.length < limit) rows.push(row);
  };

  payload.data.forEach((raw, traceIndex) => {
    const trace = asRecord(raw);
    const type = typeof trace.type === "string" ? trace.type : "scatter";
    const series =
      typeof trace.name === "string" && trace.name !== "" ? trace.name : `trace ${traceIndex + 1}`;
    const x = values(trace.x);
    const y = values(trace.y);

    if (type === "table") {
      const header = values(asRecord(trace.header).values).map((value, index) =>
        cell(value) === null ? `column ${index + 1}` : String(cell(value)),
      );
      const cellColumns = values(asRecord(trace.cells).values).map((column) => values(column));
      const rowCount = Math.max(
        cellColumns[0]?.length ?? 0,
        ...cellColumns.map((column) => column.length),
      );
      const keys = header.map((_, index) => `table_${index}`);
      dynamicLabels = Object.fromEntries(keys.map((key, index) => [key, header[index]]));
      for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
        const row: FigureRow = {
          series: String(cell(cellColumns[0]?.[rowIndex]) ?? `row ${rowIndex + 1}`),
        };
        for (let columnIndex = 1; columnIndex < cellColumns.length; columnIndex += 1) {
          row[keys[columnIndex]] = cell(cellColumns[columnIndex]?.[rowIndex]);
        }
        add(row);
      }
      return;
    }

    if (type === "heatmap") {
      const grid = heatmapGrid(trace);
      grid.forEach((zRow, rowIndex) => {
        zRow.forEach((value, columnIndex) => {
          add({
            series,
            x: cell(x[columnIndex] ?? columnIndex),
            y: cell(y[rowIndex] ?? rowIndex),
            value: cell(value),
          });
        });
      });
      return;
    }

    if (type === "funnel") {
      const stages = y.length > 0 ? y : values(trace.labels);
      const funnelValues = x.length > 0 ? x : values(trace.values);
      const count = Math.max(stages.length, funnelValues.length);
      for (let index = 0; index < count; index += 1) {
        add({
          series,
          stage: cell(stages[index] ?? index),
          value: cell(funnelValues[index]),
        });
      }
      return;
    }

    if (type === "histogram") {
      const samples = trace.orientation === "h" ? y : x;
      samples.forEach((sample) => add({ series, sample: cell(sample) }));
      return;
    }

    if (
      type === "scattergeo" ||
      type === "scattermap" ||
      type === "scattermapbox" ||
      type === "choropleth" ||
      type === "choroplethmap" ||
      type === "choroplethmapbox"
    ) {
      const longitudes = values(trace.lon);
      const latitudes = values(trace.lat);
      const locations = values(trace.locations);
      const labels = values(trace.text);
      const marker = asRecord(trace.marker);
      const mapValues = values(trace.z).length > 0 ? values(trace.z) : values(marker.color);
      const count = Math.max(
        longitudes.length,
        latitudes.length,
        locations.length,
        labels.length,
        mapValues.length,
      );
      for (let index = 0; index < count; index += 1) {
        add({
          series,
          location: cell(locations[index]),
          longitude: cell(longitudes[index]),
          latitude: cell(latitudes[index]),
          label: cell(labels[index]),
          value: cell(mapValues[index]),
        });
      }
      return;
    }

    if (type === "pie") {
      const labels = values(trace.labels);
      const pieValues = values(trace.values);
      const count = Math.max(labels.length, pieValues.length);
      for (let index = 0; index < count; index += 1) {
        add({ series, label: cell(labels[index] ?? index), value: cell(pieValues[index]) });
      }
      return;
    }

    // Lines, scatters and vertical/horizontal bars retain their actual x/y
    // coordinates. Plotly defaults a missing x array to zero-based indices.
    const count = Math.max(x.length, y.length);
    for (let index = 0; index < count; index += 1) {
      add({ series, x: cell(x.length > 0 ? x[index] : index), y: cell(y[index]) });
    }
  });

  const hasValues = (column: string) =>
    rows.some((row) => row[column] !== null && row[column] !== undefined);
  const columns = [
    ...COLUMN_ORDER.filter((column) => column === "series" || hasValues(column)),
    ...Object.keys(dynamicLabels ?? {}).filter((column) => !COLUMN_ORDER.includes(column) && hasValues(column)),
  ];
  return { columns, rows, total, labels: dynamicLabels };
}

function csvCell(value: Cell | undefined): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function figureCsv(payload: PlotlyPayload): string {
  const { columns, rows, labels } = figureData(payload);
  const header = columns.map((column) => labels?.[column] ?? COLUMN_LABELS[column] ?? column).join(",");
  const body = rows.map((row) => columns.map((column) => csvCell(row[column])).join(","));
  return [header, ...body].join("\r\n");
}

function displayCell(value: Cell | undefined): string {
  return value === null || value === undefined ? "—" : String(value);
}

type DataStatus =
  | { state: "loading" }
  | { state: "ok"; payload: PlotlyPayload }
  | { state: "unavailable" };

/** Generic story figure with a visual chart and a non-visual point-data alternative. */
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
  const table = data.state === "ok" ? figureData(data.payload, MAX_TABLE_ROWS) : null;
  const xTitle = data.state === "ok" ? axisTitle(asRecord(data.payload.layout).xaxis) : null;
  const yTitle = data.state === "ok" ? axisTitle(asRecord(data.payload.layout).yaxis) : null;
  const onPayload = (payload: PlotlyPayload | null) =>
    setData(payload ? { state: "ok", payload } : { state: "unavailable" });

  const downloadCsv = () => {
    if (data.state !== "ok") return;
    const blob = new Blob([figureCsv(data.payload)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${name.replace(/[^a-zA-Z0-9._-]/g, "_")}.csv`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="figure-card">
      <EChartsFigure pid={pid} name={name} accessibleName={caption} onPayload={onPayload} />
      <footer className="figure-card-band">
        <span className="figure-id">fig :: {name}</span>
        {caption && <p className="figure-comment">{caption}</p>}
        <details className="figure-data">
          <summary>view data table</summary>
          {data.state === "ok" && table && table.rows.length > 0 ? (
            <>
              <div
                className="table-scroll"
                role="region"
                aria-label={`Data table for ${name}`}
                tabIndex={0}
              >
                <table className="data-table">
                  <caption>
                    {xTitle !== null && <>x: {xTitle}</>}
                    {xTitle !== null && yTitle !== null && " · "}
                    {yTitle !== null && <>y: {yTitle}</>}
                    {(xTitle !== null || yTitle !== null) && " · "}
                    {table.total.toLocaleString("en-US")} plotted values
                  </caption>
                  <thead>
                    <tr>
                      {table.columns.map((column) => (
                        <th scope="col" key={column}>
                          {columnLabel(table, column)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {table.rows.map((row, index) => (
                      <tr key={index}>
                        {table.columns.map((column) =>
                          column === "series" ? (
                            <th scope="row" key={column}>
                              {row.series}
                            </th>
                          ) : (
                            <td key={column}>{displayCell(row[column])}</td>
                          ),
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {table.total > table.rows.length && (
                <p className="figure-data-note">
                  Showing the first {table.rows.length.toLocaleString("en-US")} of{" "}
                  {table.total.toLocaleString("en-US")} plotted values. The CSV contains all values.
                </p>
              )}
              <button type="button" className="figure-data-download" onClick={downloadCsv}>
                download CSV ({table.total.toLocaleString("en-US")} values)
              </button>
            </>
          ) : (
            <p className="figure-data-note">
              {data.state === "loading"
                ? "loading figure data…"
                : "data table unavailable for this figure"}
            </p>
          )}
        </details>
      </footer>
    </div>
  );
}
