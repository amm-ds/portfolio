import type {
  AnalysisResponse,
  DocumentRecord,
  Evidence,
  PageAnalysis,
  PageAnalysisResult,
  PageChatResponse,
} from "../api/types";

export const resolvedEvidence: Evidence = {
  quote: "Northwind Labs reduced processing time by 32%.",
  page: 1,
  bbox: [72, 72, 180, 88],
  resolved: true,
};

export const pageTwoEvidence: Evidence = {
  quote: "Ada Example led the regional operations review.",
  page: 2,
  bbox: [72, 110, 260, 126],
  resolved: true,
};

export const unresolvedEvidence: Evidence = {
  quote: "regional throughput chart",
  page: 1,
  bbox: null,
  resolved: false,
};

export function makePageAnalysis(page: number, overrides: Partial<PageAnalysis> = {}): PageAnalysis {
  return {
    page,
    status: "completed",
    error: null,
    issues: [],
    summary: {
      summary: `Page ${page} describes operational outcomes with cited figures.`,
      key_points: [
        { text: "Processing time fell by 32%.", evidence: [resolvedEvidence] },
        { text: "Ada Example led the regional review.", evidence: [pageTwoEvidence] },
      ],
    },
    entities: [
      { text: "Northwind Labs", name: "Northwind Labs", type: "organization", evidence: resolvedEvidence },
      { text: "Ada Example", name: "Ada Example", type: "person", evidence: pageTwoEvidence },
      { text: "ada@northwind.dev", name: "ada@northwind.dev", type: "email", evidence: resolvedEvidence },
    ],
    topics: [
      { label: "process improvement", rationale: "It quantifies a faster operating process.", evidence: [resolvedEvidence] },
      { label: "chart evidence", rationale: "A figure is referenced without resolved coordinates.", evidence: [unresolvedEvidence] },
    ],
    text_chars: 1840,
    image_count: 1,
    table_count: 0,
    ...overrides,
  };
}

export const pageOneAnalysis: PageAnalysis = makePageAnalysis(1);
export const pageTwoAnalysis: PageAnalysis = makePageAnalysis(2, {
  summary: {
    summary: "Page 2 names the review owner and schedule.",
    key_points: [{ text: "Ada Example led the regional review.", evidence: [pageTwoEvidence] }],
  },
  image_count: 0,
  table_count: 1,
});

export const failedPageAnalysis: PageAnalysis = makePageAnalysis(3, {
  status: "failed",
  error: "table model timed out",
  summary: { summary: "", key_points: [] },
  entities: [],
  topics: [],
  text_chars: 0,
  image_count: 0,
  table_count: 0,
});

export const analysisResult: PageAnalysisResult = {
  schema_version: "page-analysis-v1",
  pages: [pageTwoAnalysis, pageOneAnalysis], // Deliberately unsorted: the UI must stabilize order.
};

export const documentRecord: DocumentRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  tenant_id: "demo",
  sha256: "a".repeat(64),
  filename: "analysis-multipage.pdf",
  content_type: "application/pdf",
  storage_key: "demo/operations-report.pdf",
  status: "completed",
  page_count: 2,
  created_at: "2026-01-10T10:00:00Z",
  updated_at: "2026-01-10T10:01:00Z",
};

export const otherDocument: DocumentRecord = {
  ...documentRecord,
  id: "66666666-6666-4666-8666-666666666666",
  filename: "regional-report.pdf",
  storage_key: "demo/regional-report.pdf",
  status: "processing",
  page_count: 3,
};

export const analysisResponse: AnalysisResponse = {
  document: documentRecord,
  analysis: analysisResult,
  progress: { page_count: 2, processed_pages: 2, failed_pages: 0 },
  analyzer: "fixture-analyzer-v1",
  created_at: "2026-01-10T10:01:00Z",
  updated_at: "2026-01-10T10:02:00Z",
};

/** First poll tick: only page 1 has been analyzed. */
export const partialAnalysisResponse: AnalysisResponse = {
  ...analysisResponse,
  document: { ...documentRecord, status: "processing" },
  analysis: { schema_version: "page-analysis-v1", pages: [pageOneAnalysis] },
  progress: { page_count: 2, processed_pages: 1, failed_pages: 0 },
};

export const uploadedAnalysisResponse: AnalysisResponse = {
  document: { ...documentRecord, status: "uploaded", page_count: null },
  analysis: null,
  progress: { page_count: 0, processed_pages: 0, failed_pages: 0 },
  analyzer: null,
  created_at: "2026-01-10T10:00:00Z",
  updated_at: "2026-01-10T10:00:05Z",
};

export const chatResponse: PageChatResponse = {
  answer: "Processing time fell by 32% under Ada Example's ownership.",
  citations: [resolvedEvidence],
};

/** The retired extraction-era payload; runtime contracts must reject it. */
export const oldAnalysisV1Payload = {
  schema_version: "analysis-v1",
  summary: { short: "Short.", detailed: "Detailed.", key_points: [] },
  entities: [],
  classification: { category: "report", rationale: "rationale", evidence: [] },
  topics: [],
};
