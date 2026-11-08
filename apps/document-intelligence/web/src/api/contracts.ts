import { DOCUMENT_STATUSES, ENTITY_TYPES, PAGE_STATUSES } from "./types";
import type {
  AnalysisProgress,
  AnalysisResponse,
  DocumentRecord,
  DocumentStatus,
  EntityType,
  Evidence,
  PageAnalysis,
  PageChatMessage,
  PageChatResponse,
  PageAnalysisResult,
  PageStatus,
  UploadResponse,
  ValidationIssue,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireRecord(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`Invalid ${label}: expected an object.`);
  return value;
}

function requireString(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`Invalid ${label}: expected a string.`);
  return value;
}

function requireOption<T extends string>(value: unknown, label: string, options: readonly T[]): T {
  const parsed = requireString(value, label);
  if (!options.includes(parsed as T)) throw new Error(`Invalid ${label}: unsupported value.`);
  return parsed as T;
}

function requireNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Invalid ${label}: expected a finite number.`);
  }
  return value;
}

function requireCount(value: unknown, label: string): number {
  const parsed = requireNumber(value, label);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`Invalid ${label}: expected a non-negative integer.`);
  }
  return parsed;
}

function requirePageNumber(value: unknown, label: string): number {
  const parsed = requireNumber(value, label);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error(`Invalid ${label}: expected a positive integer.`);
  }
  return parsed;
}

function requireArray(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`Invalid ${label}: expected an array.`);
  return value;
}

function requireNullableString(value: unknown, label: string): string | null {
  return value === null ? null : requireString(value, label);
}

export function parseEvidence(input: unknown): Evidence {
  const value = requireRecord(input, "evidence");
  requireString(value.quote, "evidence.quote");
  if (typeof value.resolved !== "boolean") throw new Error("Invalid evidence.resolved: expected a boolean.");
  if (value.page !== null) requirePageNumber(value.page, "evidence.page");
  if (value.bbox !== null) {
    const box = requireArray(value.bbox, "evidence.bbox");
    if (box.length !== 4) throw new Error("Invalid evidence.bbox: expected four coordinates.");
    box.forEach((coordinate) => requireNumber(coordinate, "evidence.bbox coordinate"));
  }
  return input as Evidence;
}

function parseEvidenceList(input: unknown, label: string): Evidence[] {
  return requireArray(input, label).map(parseEvidence);
}

function parseCitedText(input: unknown): void {
  const value = requireRecord(input, "cited text");
  requireString(value.text, "cited text.text");
  parseEvidenceList(value.evidence, "cited text.evidence");
}

function parseValidationIssue(input: unknown): ValidationIssue {
  const value = requireRecord(input, "validation issue");
  requireString(value.code, "validation issue.code");
  requireString(value.path, "validation issue.path");
  requireString(value.message, "validation issue.message");
  if (value.severity !== "error" && value.severity !== "warning") {
    throw new Error("Invalid validation issue.severity.");
  }
  return input as ValidationIssue;
}

export function parsePageAnalysis(input: unknown): PageAnalysis {
  const value = requireRecord(input, "page analysis");
  requirePageNumber(value.page, "page analysis.page");
  requireOption<PageStatus>(value.status, "page analysis.status", PAGE_STATUSES);
  requireNullableString(value.error, "page analysis.error");
  requireArray(value.issues, "page analysis.issues").forEach(parseValidationIssue);

  const summary = requireRecord(value.summary, "page analysis.summary");
  requireString(summary.summary, "page analysis.summary.summary");
  requireArray(summary.key_points, "page analysis.summary.key_points").forEach(parseCitedText);

  requireArray(value.entities, "page analysis.entities").forEach((item) => {
    const entity = requireRecord(item, "page entity");
    requireString(entity.text, "page entity.text");
    requireString(entity.name, "page entity.name");
    requireOption<EntityType>(entity.type, "page entity.type", ENTITY_TYPES);
    parseEvidence(entity.evidence);
  });

  requireArray(value.topics, "page analysis.topics").forEach((item) => {
    const topic = requireRecord(item, "page topic");
    requireString(topic.label, "page topic.label");
    requireString(topic.rationale, "page topic.rationale");
    parseEvidenceList(topic.evidence, "page topic.evidence");
  });

  requireCount(value.text_chars, "page analysis.text_chars");
  requireCount(value.image_count, "page analysis.image_count");
  requireCount(value.table_count, "page analysis.table_count");
  return input as PageAnalysis;
}

export function parsePageAnalysisResult(input: unknown): PageAnalysisResult {
  const value = requireRecord(input, "page analysis result");
  if (value.schema_version !== "page-analysis-v1") {
    throw new Error(`Unsupported page analysis schema: ${String(value.schema_version)}.`);
  }
  requireArray(value.pages, "page analysis result.pages").forEach(parsePageAnalysis);
  return input as PageAnalysisResult;
}

function parseAnalysisProgress(input: unknown): AnalysisProgress {
  const value = requireRecord(input, "analysis progress");
  requireCount(value.page_count, "analysis progress.page_count");
  requireCount(value.processed_pages, "analysis progress.processed_pages");
  requireCount(value.failed_pages, "analysis progress.failed_pages");
  return input as AnalysisProgress;
}

export function parseDocumentRecord(input: unknown): DocumentRecord {
  const value = requireRecord(input, "document record");
  requireString(value.id, "document record.id");
  requireString(value.tenant_id, "document record.tenant_id");
  requireString(value.sha256, "document record.sha256");
  requireString(value.filename, "document record.filename");
  requireString(value.content_type, "document record.content_type");
  requireString(value.storage_key, "document record.storage_key");
  requireOption<DocumentStatus>(value.status, "document record.status", DOCUMENT_STATUSES);
  if (value.page_count !== null) requireCount(value.page_count, "document record.page_count");
  requireString(value.created_at, "document record.created_at");
  requireString(value.updated_at, "document record.updated_at");
  return input as DocumentRecord;
}

export function parseAnalysisResponse(input: unknown): AnalysisResponse {
  const value = requireRecord(input, "analysis response");
  parseDocumentRecord(value.document);
  if (value.analysis !== null) parsePageAnalysisResult(value.analysis);
  parseAnalysisProgress(value.progress);
  requireNullableString(value.analyzer, "analysis response.analyzer");
  requireString(value.created_at, "analysis response.created_at");
  requireString(value.updated_at, "analysis response.updated_at");
  return input as AnalysisResponse;
}

export function parsePageChatMessage(input: unknown): PageChatMessage {
  const value = requireRecord(input, "page chat message");
  if (value.role !== "user" && value.role !== "assistant") {
    throw new Error("Invalid page chat message.role.");
  }
  requireString(value.content, "page chat message.content");
  return input as PageChatMessage;
}

export function parsePageChatResponse(input: unknown): PageChatResponse {
  const value = requireRecord(input, "page chat response");
  requireString(value.answer, "page chat response.answer");
  parseEvidenceList(value.citations, "page chat response.citations");
  return input as PageChatResponse;
}

export function parseUploadResponse(input: unknown): UploadResponse {
  const value = requireRecord(input, "upload response");
  parseDocumentRecord(value.document);
  if (typeof value.duplicate !== "boolean") throw new Error("Invalid upload response.duplicate.");
  requireNullableString(value.job_id, "upload response.job_id");
  return input as UploadResponse;
}
