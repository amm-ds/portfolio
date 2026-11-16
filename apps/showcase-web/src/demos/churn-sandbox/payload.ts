import { getDemoPayload } from "../../api";
import type { ChurnPayload, ConfusionRow } from "../types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function hasNumbers(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => isNumber(value[key]));
}

function hasStrings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof value[key] === "string");
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isConfusionRow(value: unknown): value is ConfusionRow {
  return isRecord(value) && hasNumbers(value, ["t", "tn", "fp", "fn", "tp"]);
}

function isRange(value: unknown): boolean {
  return isRecord(value) && hasNumbers(value, ["min", "max"]);
}

function isChurnPayload(value: unknown): value is ChurnPayload {
  if (!isRecord(value) || !hasStrings(value, ["demo", "project"]) ||
    !hasNumbers(value, ["holdout_n", "roc_auc"])) return false;
  if (!isRecord(value.model) || !hasStrings(value.model, ["name"]) ||
    !hasNumbers(value.model, ["roc_auc", "ece", "threshold_default", "threshold_selected"])) {
    return false;
  }
  if (!isRecord(value.cost_model) || !hasStrings(value.cost_model, ["note"]) ||
    !hasNumbers(value.cost_model, ["fp_cost", "fn_cost"])) return false;
  if (!isRecord(value.headline) ||
    !hasNumbers(value.headline, ["cost_naive", "cost_selected"]) ||
    !isRecord(value.headline.delta_ci) ||
    !hasNumbers(value.headline.delta_ci, ["point", "lo", "hi"]) ||
    typeof value.headline.delta_ci.significant_95 !== "boolean") return false;
  if (!Array.isArray(value.thresholds) || !value.thresholds.every(isNumber) ||
    !Array.isArray(value.overall) || !value.overall.every(isConfusionRow) ||
    value.thresholds.length === 0 || value.overall.length !== value.thresholds.length) return false;
  if (!isRecord(value.slices) || !Object.values(value.slices).every((groups) =>
    isRecord(groups) && Object.values(groups).every((rows) =>
      Array.isArray(rows) && rows.every(isConfusionRow)))) return false;
  if (!Array.isArray(value.calibration) || !value.calibration.every((bin) =>
    isRecord(bin) && hasNumbers(bin, ["bin_lo", "bin_hi", "n", "mean_predicted", "observed"]))) {
    return false;
  }
  if (!Array.isArray(value.customers) || value.customers.length === 0 ||
    !value.customers.every((customer) => isRecord(customer) && hasStrings(customer, ["label"]) &&
      hasNumbers(customer, ["churn_probability"]) && isRecord(customer.features) &&
      hasStrings(customer.features, ["contract", "internet_service"]) &&
      hasNumbers(customer.features, ["tenure_months", "monthly_charges"]))) return false;
  const domains = value.feature_domains;
  return isRecord(domains) && isRange(domains.tenure_months) &&
    isRange(domains.monthly_charges) && isStringArray(domains.contract) &&
    isStringArray(domains.internet_service);
}

/** Fetch and validate the legacy-v1 churn payload (`GET /demos/{id}/payload`). */
export async function fetchChurnPayload(
  demoId: string,
  signal?: AbortSignal,
): Promise<ChurnPayload> {
  const value = await getDemoPayload(demoId, signal);
  const version = isRecord(value) ? value.schema_version : undefined;
  // The committed v1 artifact predates the field; explicit newer versions are not compatible.
  if (version !== undefined && version !== 1) {
    throw new Error(`unsupported churn payload schema_version: ${String(version)}`);
  }
  if (!isChurnPayload(value)) throw new Error("invalid churn demo payload");
  return value;
}
