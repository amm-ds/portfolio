import { RUN_STATUSES } from "./types";
import type { Dataset, RunCase, RunDetail, RunMetrics, RunStatus, RunSummary } from "./types";

function requireRecord(input: unknown, label: string): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    throw new Error(`Invalid ${label}: expected an object.`);
  }
  return input as Record<string, unknown>;
}

function requireArray(input: unknown, label: string): unknown[] {
  if (!Array.isArray(input)) throw new Error(`Invalid ${label}: expected an array.`);
  return input;
}

function requireString(input: unknown, label: string): string {
  if (typeof input !== "string" || input.length === 0) {
    throw new Error(`Invalid ${label}: expected a non-empty string.`);
  }
  return input;
}

function requireNullableString(input: unknown, label: string): string | null {
  return input === null ? null : requireString(input, label);
}

function requireNumber(input: unknown, label: string): number {
  if (typeof input !== "number" || !Number.isFinite(input)) {
    throw new Error(`Invalid ${label}: expected a finite number.`);
  }
  return input;
}

function requireCount(input: unknown, label: string): number {
  const value = requireNumber(input, label);
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`Invalid ${label}: expected a non-negative integer.`);
  }
  return value;
}

function requireScore(input: unknown, label: string): number {
  const value = requireNumber(input, label);
  if (value < 0 || value > 1) throw new Error(`Invalid ${label}: expected a score from 0 to 1.`);
  return value;
}

function requireNonNegative(input: unknown, label: string): number {
  const value = requireNumber(input, label);
  if (value < 0) throw new Error(`Invalid ${label}: expected a non-negative number.`);
  return value;
}

function parseMetrics(input: unknown): RunMetrics {
  const value = requireRecord(input, "run metrics");
  requireScore(value.accuracy, "run metrics.accuracy");
  requireScore(value.f1, "run metrics.f1");
  requireNonNegative(value.p95_latency_ms, "run metrics.p95_latency_ms");
  requireNonNegative(value.cost_usd, "run metrics.cost_usd");
  return input as RunMetrics;
}

function parseRunSummary(input: unknown): RunSummary {
  const value = requireRecord(input, "run");
  requireString(value.id, "run.id");
  requireString(value.dataset_id, "run.dataset_id");
  requireString(value.model, "run.model");
  const status = requireString(value.status, "run.status") as RunStatus;
  if (!RUN_STATUSES.includes(status)) throw new Error("Invalid run.status: unsupported value.");
  requireCount(value.case_count, "run.case_count");
  requireCount(value.failed_cases, "run.failed_cases");
  if (value.metrics !== null) parseMetrics(value.metrics);
  requireString(value.created_at, "run.created_at");
  requireNullableString(value.completed_at, "run.completed_at");
  return input as RunSummary;
}

function parseRunCase(input: unknown): RunCase {
  const value = requireRecord(input, "run case");
  requireString(value.id, "run case.id");
  requireString(value.input, "run case.input");
  requireString(value.expected, "run case.expected");
  requireNullableString(value.output, "run case.output");
  if (typeof value.passed !== "boolean") throw new Error("Invalid run case.passed: expected a boolean.");
  requireNonNegative(value.latency_ms, "run case.latency_ms");
  requireNullableString(value.error, "run case.error");
  return input as RunCase;
}

export function parseDatasets(input: unknown): Dataset[] {
  return requireArray(input, "dataset list").map((item) => {
    const value = requireRecord(item, "dataset");
    requireString(value.id, "dataset.id");
    requireString(value.name, "dataset.name");
    requireString(value.version, "dataset.version");
    requireString(value.description, "dataset.description");
    requireCount(value.case_count, "dataset.case_count");
    requireArray(value.tags, "dataset.tags").forEach((tag) => requireString(tag, "dataset tag"));
    requireString(value.created_at, "dataset.created_at");
    return item as Dataset;
  });
}

export function parseRuns(input: unknown): RunSummary[] {
  return requireArray(input, "run list").map(parseRunSummary);
}

export function parseRunDetail(input: unknown): RunDetail {
  parseRunSummary(input);
  const value = requireRecord(input, "run");
  requireArray(value.cases, "run.cases").forEach(parseRunCase);
  return input as RunDetail;
}
