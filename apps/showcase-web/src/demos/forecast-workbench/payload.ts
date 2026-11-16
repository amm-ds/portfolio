import { getDemoPayload } from "../../api";
import type { CatalogEntry, ForecastWindow, ForecastWorkbenchPayload } from "../types";

const FORECAST_SCHEMA_VERSION = 4;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every(isNumber);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function hasStrings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof value[key] === "string");
}

function hasNumbers(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => isNumber(value[key]));
}

function isNumberArrays(value: unknown): value is Record<string, number[]> {
  return isRecord(value) && Object.values(value).every(isNumberArray);
}

function isWindow(value: unknown): value is ForecastWindow {
  if (!isRecord(value)) return false;
  const { actual, curves, wape, band } = value;
  if (!isNumberArray(value.history) || !isNumberArray(actual) || !isNumberArrays(curves) ||
    !isRecord(wape) || !Object.values(wape).every(isNumber) || !isRecord(band)) return false;
  const { lo, hi } = band;
  if (!isNumberArray(lo) || !isNumberArray(hi)) return false;
  return actual.length > 0 &&
    Object.values(curves).every((curve) => curve.length === actual.length) &&
    lo.length === actual.length && hi.length === actual.length;
}

function isCatalogEntry(value: unknown): value is CatalogEntry {
  return isRecord(value) && hasStrings(value, ["series_id", "store", "class", "half"]) &&
    hasNumbers(value, ["adi", "cv2", "units_last_28d"]) &&
    ["dense", "intermittent"].includes(String(value.class)) &&
    ["top_units", "bottom_intermittency"].includes(String(value.half)) &&
    isWindow(value.windows);
}

function isGroups(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const { headline, test_pooled, test_by_class, win_rate_vs_naive, stability, classes, ensemble,
    band, _scope } = value;
  if (!isRecord(headline) || !hasStrings(headline, ["metric", "champion"]) ||
    !hasNumbers(headline, ["champion_wrmsse", "absolute_ensemble_wrmsse"]) ||
    !isRecord(headline.wrmsse_champion) || !isRecord(headline.convex_ensemble_vs_naive)) {
    return false;
  }
  if (!isRecord(test_pooled) || !Object.values(test_pooled).every((metrics) =>
    isRecord(metrics) && hasNumbers(metrics,
      ["wape", "wrmsse", "bias", "zero_day_accuracy", "zero_day_accuracy_intermittent"]))) {
    return false;
  }
  if (!isRecord(test_by_class) || !isRecord(win_rate_vs_naive) || !isRecord(stability) ||
    !Object.values(stability).every(isNumber)) return false;
  if (!isRecord(classes) || !isRecord(classes.counts) || !isRecord(classes.thresholds) ||
    !hasNumbers(classes.counts, ["dense", "intermittent"]) ||
    !hasNumbers(classes.thresholds, ["adi", "cv2"])) return false;
  if (!isRecord(ensemble) || !isStringArray(ensemble.pool) || !isStringArray(ensemble.members) ||
    !isNumberArray(ensemble.weights) || !hasStrings(ensemble, ["rule"]) ||
    !isRecord(ensemble.selection_screen)) return false;
  if (!isRecord(band) || !hasStrings(band, ["method"]) ||
    !isNumberArray(band.per_horizon_width) || !isNumberArray(band.per_horizon_coverage) ||
    !isRecord(band.candidates)) return false;
  return isRecord(_scope) && Object.values(_scope).every((note) => typeof note === "string");
}

function isForecastPayload(value: unknown): value is ForecastWorkbenchPayload {
  if (!isRecord(value) || !hasStrings(value, ["demo", "project", "protocol", "catalog_rule",
    "curve_provenance"]) || !hasNumbers(value, ["history_days"]) || !isGroups(value.groups)) {
    return false;
  }
  if (!Array.isArray(value.catalog) || value.catalog.length === 0 ||
    !value.catalog.every(isCatalogEntry)) return false;
  if (!Array.isArray(value.origins) || value.origins.length === 0 ||
    !value.origins.every((origin) => isRecord(origin) &&
      hasStrings(origin, ["origin", "history_start"]) && isStringArray(origin.forecast_dates))) {
    return false;
  }
  const metadata = value.evaluation_metadata;
  return isRecord(metadata) && hasStrings(metadata, ["protocol"]) &&
    isRecord(metadata.dataset) && isRecord(metadata.split) && isRecord(metadata.seeds) &&
    Object.values(metadata.seeds).every(isNumber);
}

/** Fetch and validate the schema-v4 forecast payload (`GET /demos/{id}/payload`). */
export async function fetchForecastPayload(
  demoId: string,
  signal?: AbortSignal,
): Promise<ForecastWorkbenchPayload> {
  const value = await getDemoPayload(demoId, signal);
  const version = isRecord(value) ? value.schema_version : undefined;
  if (version !== FORECAST_SCHEMA_VERSION) {
    throw new Error(`unsupported forecast payload schema_version: ${String(version)}`);
  }
  if (!isForecastPayload(value)) throw new Error("invalid forecast demo payload");
  return value;
}
