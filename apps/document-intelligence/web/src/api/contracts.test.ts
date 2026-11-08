import { describe, expect, it } from "vitest";
import type { Evidence } from "./types";
import {
  analysisResponse,
  chatResponse,
  failedPageAnalysis,
  oldAnalysisV1Payload,
  pageOneAnalysis,
  partialAnalysisResponse,
  resolvedEvidence,
  uploadedAnalysisResponse,
} from "../test/fixtures";
import {
  parseAnalysisResponse,
  parsePageAnalysis,
  parsePageAnalysisResult,
  parsePageChatMessage,
  parsePageChatResponse,
} from "./contracts";

describe("page-analysis-v1 runtime contracts", () => {
  it("accepts a complete response and preserves exact evidence coordinates", () => {
    expect(parseAnalysisResponse(analysisResponse)).toEqual(analysisResponse);
  });

  it("sorts nothing but tolerates pages arriving out of order", () => {
    const parsed = parseAnalysisResponse(analysisResponse);
    expect(parsed.analysis?.pages.map((page) => page.page)).toEqual([2, 1]);
  });

  it("accepts a null analysis while the document is still uploaded", () => {
    expect(parseAnalysisResponse(uploadedAnalysisResponse)).toEqual(uploadedAnalysisResponse);
  });

  it("accepts partial progress and failed pages honestly", () => {
    expect(parseAnalysisResponse(partialAnalysisResponse)).toEqual(partialAnalysisResponse);
    expect(parsePageAnalysis(failedPageAnalysis).status).toBe("failed");
  });

  it("rejects the retired analysis-v1 extraction payload", () => {
    expect(() => parsePageAnalysisResult(oldAnalysisV1Payload)).toThrow(/Unsupported page analysis schema/);
    const legacy = { ...analysisResponse, analysis: oldAnalysisV1Payload };
    expect(() => parseAnalysisResponse(legacy)).toThrow(/Unsupported page analysis schema/);
  });

  it("rejects unknown schema versions", () => {
    expect(() => parsePageAnalysisResult({ schema_version: "page-analysis-v2", pages: [] })).toThrow(
      /Unsupported page analysis schema/,
    );
  });

  it("rejects invalid page numbers, statuses, and counters", () => {
    expect(() => parsePageAnalysis({ ...pageOneAnalysis, page: 0 })).toThrow(/page analysis.page/);
    expect(() => parsePageAnalysis({ ...pageOneAnalysis, page: 1.5 })).toThrow(/page analysis.page/);
    expect(() =>
      parsePageAnalysis({ ...pageOneAnalysis, status: "pending_review" as never }),
    ).toThrow(/page analysis.status/);
    expect(() => parsePageAnalysis({ ...pageOneAnalysis, text_chars: -1 })).toThrow(/text_chars/);
    expect(() => parsePageAnalysis({ ...pageOneAnalysis, image_count: 0.5 })).toThrow(/image_count/);
  });

  it("rejects invalid evidence geometry and severities", () => {
    const badBbox = structuredClone(pageOneAnalysis);
    badBbox.summary.key_points[0].evidence[0].bbox = [1, 2] as unknown as Evidence["bbox"];
    expect(() => parsePageAnalysis(badBbox)).toThrow(/bbox/);

    const badSeverity = structuredClone(pageOneAnalysis);
    badSeverity.issues = [
      { code: "unresolved_evidence", path: "summary.key_points[0]", message: "quote not found", severity: "critical" as never },
    ];
    expect(() => parsePageAnalysis(badSeverity)).toThrow(/severity/);
  });

  it("rejects unknown entity types and malformed topics", () => {
    const badType = structuredClone(pageOneAnalysis);
    badType.entities[0].type = "unknown_type" as never;
    expect(() => parsePageAnalysis(badType)).toThrow(/page entity.type/);

    const badTopic = structuredClone(pageOneAnalysis);
    badTopic.topics[0].rationale = 42 as unknown as string;
    expect(() => parsePageAnalysis(badTopic)).toThrow(/page topic.rationale/);
  });

  it("rejects document statuses outside the analysis lifecycle", () => {
    const stale = structuredClone(analysisResponse);
    stale.document.status = "needs_review" as never;
    expect(() => parseAnalysisResponse(stale)).toThrow(/document record.status/);
  });

  it("validates chat messages and exact answer citations", () => {
    expect(parsePageChatResponse(chatResponse)).toEqual(chatResponse);
    expect(() =>
      parsePageChatResponse({ answer: "ok", citations: [{ ...resolvedEvidence, page: 0 }] }),
    ).toThrow(/page/);
    expect(() => parsePageChatMessage({ role: "system", content: "nope" })).toThrow(/role/);
  });
});
