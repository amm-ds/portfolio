import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";
import {
  analysisResponse,
  chatResponse,
  documentRecord,
  oldAnalysisV1Payload,
  resolvedEvidence,
} from "../test/fixtures";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "x-request-id": "req-test" },
  });
}

describe("API client page-analysis contracts", () => {
  it("adds development identity headers and validates the document list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([documentRecord]));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.documents()).resolves.toEqual([documentRecord]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/documents");
    const headers = new Headers(init.headers);
    expect(headers.get("X-Dev-Tenant")).toBe("demo");
    expect(headers.get("X-Dev-Actor")).toBe("developer");
  });

  it("rejects document records with retired review-era statuses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse([{ ...documentRecord, status: "pending_review" }])),
    );
    await expect(api.documents()).rejects.toThrow(/document record.status/);
  });

  it("loads and validates the page analysis endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(analysisResponse));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.analysis("doc-id")).resolves.toEqual(analysisResponse);
    expect(fetchMock.mock.calls[0][0]).toBe("/documents/doc-id/analysis");
  });

  it("refuses retired analysis-v1 payloads from the analysis endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ ...analysisResponse, analysis: oldAnalysisV1Payload })),
    );
    await expect(api.analysis("doc-id")).rejects.toThrow(/Unsupported page analysis schema/);
  });

  it("posts reanalysis at the analysis-only route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ accepted: true }, 202));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.reanalyze("doc-id")).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0][0]).toBe("/documents/doc-id/reanalyze");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
  });

  it("posts the bounded chat history to the page chat route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(chatResponse));
    vi.stubGlobal("fetch", fetchMock);
    const messages = [
      { role: "user" as const, content: "Who led the review?" },
      { role: "assistant" as const, content: "Ada Example." },
      { role: "user" as const, content: "By how much did processing time fall?" },
    ];
    await expect(api.pageChat("doc-id", 2, messages)).resolves.toEqual(chatResponse);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/documents/doc-id/pages/2/chat");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ messages });
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("validates chat answers with exact citations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ answer: "ok", citations: [{ ...resolvedEvidence, resolved: "yes" }] })),
    );
    await expect(api.pageChat("doc-id", 1, [{ role: "user", content: "q" }])).rejects.toThrow(/resolved/);
  });

  it("downloads full-document and single-page exports", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('{"schema_version":"page-analysis-v1"}', { status: 200 }))
      .mockResolvedValueOnce(new Response("# Page analysis", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const jsonBlob = await api.exportAnalysis("doc-id", "json");
    const mdBlob = await api.exportPage("doc-id", 2, "md");
    expect(jsonBlob.size).toBeGreaterThan(0);
    expect(mdBlob.size).toBeGreaterThan(0);
    expect(fetchMock.mock.calls[0][0]).toBe("/documents/doc-id/analysis/export?format=json");
    expect(fetchMock.mock.calls[1][0]).toBe("/documents/doc-id/pages/2/export?format=md");
  });

  it("preserves duplicate upload semantics", async () => {
    const duplicate = { document: documentRecord, duplicate: true, job_id: null };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(duplicate, 201));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["%PDF-test"], "analysis-multipage.pdf", { type: "application/pdf" });
    await expect(api.upload(file)).resolves.toEqual(duplicate);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toMatchObject({ name: "analysis-multipage.pdf" });
  });

  it("rejects uploads whose document record fails validation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ document: { ...documentRecord, status: "approved" }, duplicate: false, job_id: null }, 201)),
    );
    const file = new File(["%PDF-test"], "analysis-multipage.pdf", { type: "application/pdf" });
    await expect(api.upload(file)).rejects.toThrow(/document record.status/);
  });

  it("exposes stable request ids from the error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "analysis_failed", message: "Analyzer crashed", request_id: "req-409" } }, 409),
      ),
    );
    const promise = api.analysis("doc-id");
    await expect(promise).rejects.toMatchObject({ status: 409, code: "analysis_failed", requestId: "req-409" });
    await promise.catch((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
    });
  });

  it("falls back honestly when an error response is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502 })));
    await expect(api.documents()).rejects.toMatchObject({ code: "http_502", message: "Request failed with HTTP 502." });
  });
});
