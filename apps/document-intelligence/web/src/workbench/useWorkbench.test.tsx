import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAT_HISTORY_LIMIT, CHAT_STORE_LIMIT, useWorkbench } from "./useWorkbench";
import type { AnalysisResponse } from "../api/types";
import {
  analysisResponse,
  documentRecord,
  otherDocument,
  pageOneAnalysis,
  pageTwoAnalysis,
} from "../test/fixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function bufferResponse(body = "%PDF-test"): Response {
  return new Response(new TextEncoder().encode(body), { status: 200 });
}

describe("useWorkbench", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("loads the library, prefers a completed document, and loads its analysis and PDF", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([otherDocument, documentRecord]);
      if (url === `/documents/${documentRecord.id}/analysis`) return jsonResponse(analysisResponse);
      if (url === `/documents/${documentRecord.id}/content`) return bufferResponse();
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});

    expect(result.current.documents).toHaveLength(2);
    expect(result.current.selectedId).toBe(documentRecord.id);
    expect(result.current.selectedAnalysis).toEqual(analysisResponse);
    expect(result.current.content).not.toBeNull();
    expect(result.current.sortedPages.map((page) => page.page)).toEqual([1, 2]);
    expect(result.current.pageCount).toBe(2);
  });

  it("keeps chat history and the selected page intact while polling merges partial pages", async () => {
    let analysisState: AnalysisResponse = {
      document: { ...documentRecord, status: "processing" },
      analysis: { schema_version: "page-analysis-v1", pages: [pageOneAnalysis] },
      progress: { page_count: 2, processed_pages: 1, failed_pages: 0 },
      analyzer: "fixture-analyzer-v1",
      created_at: "2026-01-10T10:01:00Z",
      updated_at: "2026-01-10T10:01:30Z",
    };
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([analysisState.document]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisState);
      if (url.endsWith("/content")) return bufferResponse();
      if (url.includes("/pages/1/chat")) return jsonResponse({ answer: "Ada Example.", citations: [] });
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});
    expect(result.current.selectedAnalysis?.analysis?.pages).toHaveLength(1);

    // Seed a conversation and move to page 2 before the next poll tick.
    await act(async () => {
      await result.current.sendChat(1, "Who led the review?");
    });
    expect(result.current.chatHistory(1)).toHaveLength(2);
    act(() => result.current.selectPage(2));
    expect(result.current.selectedPage).toBe(2);

    // Second poll tick completes page 2; chat and selection must survive.
    analysisState = {
      ...analysisState,
      document: { ...analysisState.document, status: "completed" },
      analysis: { schema_version: "page-analysis-v1", pages: [pageTwoAnalysis, pageOneAnalysis] },
      progress: { page_count: 2, processed_pages: 2, failed_pages: 0 },
    };
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });

    expect(result.current.selectedAnalysis?.analysis?.pages).toHaveLength(2);
    expect(result.current.selectedPage).toBe(2);
    expect(result.current.chatHistory(1)).toHaveLength(2);
    expect(result.current.chatHistory(1)[0]).toMatchObject({ role: "user", content: "Who led the review?" });
  });

  it("sends only the bounded tail of the chat history", async () => {
    let chatBody = null as null | { messages: Array<{ role: string; content: string }> };
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      if (url.includes("/pages/1/chat")) {
        chatBody = JSON.parse(String(init?.body));
        return jsonResponse({ answer: "Answer.", citations: [] });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});

    // Twelve exchanges produce 24 stored messages; the API request must carry only the
    // most recent CHAT_HISTORY_LIMIT of them, starting with a user turn.
    for (let index = 0; index < 12; index += 1) {
      await act(async () => {
        await result.current.sendChat(1, `question ${index}`);
      });
    }
    expect(chatBody?.messages.length).toBe(CHAT_HISTORY_LIMIT);
    expect(chatBody?.messages[0]).toEqual({ role: "assistant", content: "Answer." });
    expect(chatBody?.messages[CHAT_HISTORY_LIMIT - 1]).toEqual({ role: "user", content: "question 11" });
  });

  it("keeps the failed user turn retryable after a chat error", async () => {
    let failChat = true;
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      if (url.includes("/pages/1/chat")) {
        if (failChat) return jsonResponse({ error: { code: "chat_failed", message: "model unavailable", request_id: null } }, 502);
        return jsonResponse({ answer: "Recovered answer.", citations: [] });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});

    await act(async () => {
      await result.current.sendChat(1, "question one");
    });
    expect(result.current.chatError).toEqual({ page: 1, message: expect.stringContaining("model unavailable") });
    expect(result.current.chatHistory(1)).toHaveLength(1); // user turn stays visible

    failChat = false;
    await act(async () => {
      result.current.retryChat(1);
    });
    await act(async () => {});
    expect(result.current.chatHistory(1)).toHaveLength(2);
    expect(result.current.chatHistory(1)[1]).toMatchObject({ role: "assistant", content: "Recovered answer." });
    expect(result.current.chatError).toBeNull();
  });

  it("clamps the selected page to the known page count", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});
    act(() => result.current.selectPage(99));
    expect(result.current.selectedPage).toBe(2);
    act(() => result.current.selectPage(0));
    expect(result.current.selectedPage).toBe(1);
  });

  it("revealing a citation jumps to its source page", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});
    act(() =>
      result.current.revealCitation({
        label: "citation",
        evidence: pageTwoAnalysis.summary.key_points[0].evidence[0],
      }),
    );
    expect(result.current.selectedPage).toBe(2);
    expect(result.current.selectedCitation?.label).toBe("citation");
  });

  it("keeps polling after a reanalyze until the worker pickup clears the keep-alive", async () => {
    let analysisState: AnalysisResponse = analysisResponse;
    let analysisCalls = 0;
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/reanalyze")) return jsonResponse({}, 202);
      if (url.endsWith("/analysis")) {
        analysisCalls += 1;
        return jsonResponse(analysisState);
      }
      if (url.endsWith("/content")) return bufferResponse();
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});
    expect(analysisCalls).toBe(1); // initial detail load only; nothing is active

    await act(async () => {
      await result.current.reanalyze(documentRecord.id);
    });
    // The 202 still leaves the record `completed`; the immediate refresh is not pickup.
    expect(analysisCalls).toBe(2);
    expect(result.current.notice).toContain("Reanalysis requested");

    // Polling runs even though the server still reports the document as completed.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(analysisCalls).toBe(3);

    // The worker picks the job up: fresh progress is observed and the keep-alive clears.
    analysisState = {
      ...analysisResponse,
      document: { ...documentRecord, status: "processing" },
      progress: { page_count: 2, processed_pages: 1, failed_pages: 0 },
    };
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(analysisCalls).toBe(4);

    // The reanalysis completes; with pickup observed and nothing active, polling stops.
    analysisState = analysisResponse;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(analysisCalls).toBe(5); // one last fetch of the completed results
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(analysisCalls).toBe(5); // an uncleared keep-alive would fetch again every tick
  });

  it("clears the previous PDF while the next document's detail loads", async () => {
    const secondDocument = {
      ...documentRecord,
      id: "22222222-2222-4222-8222-222222222222",
      filename: "second-report.pdf",
    };
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord, secondDocument]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});
    expect(result.current.selectedId).toBe(documentRecord.id);
    expect(result.current.content).not.toBeNull();

    act(() => result.current.selectDocument(secondDocument.id));
    // The stale PDF must not linger under the new document's title.
    expect(result.current.content).toBeNull();

    await act(async () => {});
    expect(result.current.content).not.toBeNull();
    expect(result.current.selectedId).toBe(secondDocument.id);
  });

  it("bounds the stored chat history so the rendered window cannot grow forever", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url.endsWith("/analysis")) return jsonResponse(analysisResponse);
      if (url.endsWith("/content")) return bufferResponse();
      if (url.includes("/pages/1/chat")) return jsonResponse({ answer: "Answer.", citations: [] });
      throw new Error(`Unexpected URL: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useWorkbench());
    await act(async () => {});

    for (let index = 0; index < 25; index += 1) {
      await act(async () => {
        await result.current.sendChat(1, `question ${index}`);
      });
    }
    // 25 exchanges are 50 turns; only the bounded window stays stored.
    expect(result.current.chatHistory(1)).toHaveLength(CHAT_STORE_LIMIT);
  });
});
