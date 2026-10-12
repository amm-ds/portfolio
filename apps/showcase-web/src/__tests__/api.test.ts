import { describe, expect, it, vi, afterEach } from "vitest";
import { getMetrics, getProjects, parseSseChunk, streamChat } from "../api";

describe("parseSseChunk", () => {
  it("parses a complete single event", () => {
    const { events, remainder } = parseSseChunk("event: text\ndata: hello\n\n", "");
    expect(events).toEqual([{ event: "text", data: "hello" }]);
    expect(remainder).toBe("");
  });

  it("parses multiple events in one chunk", () => {
    const chunk = "event: text\ndata: foo\n\nevent: result\ndata: {\"a\":1}\n\n";
    const { events } = parseSseChunk(chunk, "");
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event: "text", data: "foo" });
    expect(events[1]).toEqual({ event: "result", data: '{"a":1}' });
  });

  it("buffers partial events across chunks", () => {
    const first = parseSseChunk("event: text\nda", "");
    expect(first.events).toEqual([]);
    expect(first.remainder).toBe("event: text\nda");

    const second = parseSseChunk("ta: partial\n\n", first.remainder);
    expect(second.events).toEqual([{ event: "text", data: "partial" }]);
    expect(second.remainder).toBe("");
  });

  it("joins multi-line data payloads", () => {
    const { events } = parseSseChunk("event: text\ndata: line1\ndata: line2\n\n", "");
    expect(events).toEqual([{ event: "text", data: "line1\nline2" }]);
  });

  it("strips a single leading space from data values", () => {
    const { events } = parseSseChunk("data: spaced\n\n", "");
    expect(events[0].data).toBe("spaced");
  });

  it("supports CRLF line endings", () => {
    const { events } = parseSseChunk("event: text\r\ndata: crlf\r\n\r\n", "");
    expect(events).toEqual([{ event: "text", data: "crlf" }]);
  });
});

describe("getProjects", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fetches /projects and returns parsed JSON", async () => {
    const payload = [
      {
        id: "01-rag-agent",
        title: "RAG Agent",
        domain: "NLP",
        techniques: ["RAG"],
        data: "docs",
        status: "flagship",
        order: 1,
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const projects = await getProjects();
    expect(fetchMock).toHaveBeenCalledWith("/projects");
    expect(projects).toEqual(payload);
  });

  it("throws on non-OK responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("nope", { status: 500 })),
    );
    await expect(getProjects()).rejects.toThrow("500");
  });
});

describe("getMetrics", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns metrics JSON on success", async () => {
    const metrics = { baseline: { f1: 0.5 } };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(metrics), { status: 200 })),
    );
    await expect(getMetrics("01-rag-agent")).resolves.toEqual(metrics);
  });

  it("returns null on 404 (pipeline not run yet)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not found", { status: 404 })),
    );
    await expect(getMetrics("05-ml-pipeline-churn")).resolves.toBeNull();
  });

  it("rethrows other errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("err", { status: 500 })),
    );
    await expect(getMetrics("01-rag-agent")).rejects.toThrow("500");
  });
});

describe("streamChat", () => {
  afterEach(() => vi.unstubAllGlobals());

  function sseResponse(chunks: string[]): Response {
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const encoder = new TextEncoder();
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });
    return new Response(stream, { status: 200 });
  }

  it("streams text deltas then emits the parsed result event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          "event: text\ndata: Hel\n\n",
          "event: text\ndata: lo\n\n",
          'event: result\ndata: {"summary":"Hello","citations":[],"confidence":0.9}\n\n',
        ]),
      ),
    );
    const onDelta = vi.fn();
    const onResult = vi.fn();
    const onError = vi.fn();
    const abort = await streamChat("hi", { onDelta, onResult, onError });
    abort();
    // let the microtask queue flush
    await new Promise((r) => setTimeout(r, 0));

    expect(fetch).toHaveBeenCalledWith(
      "/rag/chat/stream",
      expect.objectContaining({ method: "POST" }),
    );
    expect(onDelta).toHaveBeenNthCalledWith(1, "Hel");
    expect(onDelta).toHaveBeenNthCalledWith(2, "lo");
    expect(onResult).toHaveBeenCalledWith({
      summary: "Hello",
      citations: [],
      confidence: 0.9,
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports an error on non-OK responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 503 })),
    );
    const onError = vi.fn();
    const abort = await streamChat("hi", { onDelta: vi.fn(), onResult: vi.fn(), onError });
    abort();
    await new Promise((r) => setTimeout(r, 0));
    expect(onError).toHaveBeenCalledWith("Request failed with 503");
  });

  it("handles a result event split across network chunks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          'event: result\nda',
          'ta: {"summary":"s","citations":[{"chunk_id":"c1","article_id":"a1","title":"T","excerpt":"E","score":0.8}],"confidence":0.7}\n\n',
        ]),
      ),
    );
    const onResult = vi.fn();
    const onError = vi.fn();
    const abort = await streamChat("q", { onDelta: vi.fn(), onResult, onError });
    abort();
    await new Promise((r) => setTimeout(r, 0));
    expect(onError).not.toHaveBeenCalled();
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onResult.mock.calls[0][0].citations[0].chunk_id).toBe("c1");
  });
});
