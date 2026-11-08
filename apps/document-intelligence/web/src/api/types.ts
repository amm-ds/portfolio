/** JSON contracts mirrored from the backend's strict Pydantic models. */
export type ISODateTime = string;
export type UUID = string;
export type BBox = [number, number, number, number];

export type DocumentStatus = "uploaded" | "processing" | "completed" | "failed";
export const DOCUMENT_STATUSES = ["uploaded", "processing", "completed", "failed"] as const;

export type PageStatus = "completed" | "failed";
export const PAGE_STATUSES = ["completed", "failed"] as const;

export const ENTITY_TYPES = [
  "person",
  "organization",
  "email",
  "date",
  "money",
  "location",
  "skill",
  "job_title",
  "equipment",
  "document_id",
  "region",
  "other",
] as const;
export type EntityType = (typeof ENTITY_TYPES)[number];

export interface Evidence {
  quote: string;
  page: number | null;
  bbox: BBox | null;
  resolved: boolean;
}

export interface CitedText {
  text: string;
  evidence: Evidence[];
}

export interface PageSummary {
  summary: string;
  key_points: CitedText[];
}

export interface PageEntity {
  text: string;
  name: string;
  type: EntityType;
  evidence: Evidence;
}

export interface PageTopic {
  label: string;
  rationale: string;
  evidence: Evidence[];
}

export interface ValidationIssue {
  code: string;
  path: string;
  message: string;
  severity: "error" | "warning";
}

export interface PageAnalysis {
  page: number;
  status: PageStatus;
  error: string | null;
  issues: ValidationIssue[];
  summary: PageSummary;
  entities: PageEntity[];
  topics: PageTopic[];
  text_chars: number;
  image_count: number;
  table_count: number;
}

export interface PageAnalysisResult {
  schema_version: "page-analysis-v1";
  pages: PageAnalysis[];
}

export interface AnalysisProgress {
  page_count: number;
  processed_pages: number;
  failed_pages: number;
}

export interface DocumentRecord {
  id: UUID;
  tenant_id: string;
  sha256: string;
  filename: string;
  content_type: string;
  storage_key: string;
  status: DocumentStatus;
  page_count: number | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AnalysisResponse {
  document: DocumentRecord;
  analysis: PageAnalysisResult | null;
  progress: AnalysisProgress;
  analyzer: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface PageChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface PageChatResponse {
  answer: string;
  citations: Evidence[];
}

export interface UploadResponse {
  document: DocumentRecord;
  duplicate: boolean;
  job_id: UUID | null;
}
