/** Narrow an unknown JSON value to a plain record; non-objects become `{}`
 *  so property reads stay total (plotly payload probing, axis titles, …). */
export function asRecord(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
}
