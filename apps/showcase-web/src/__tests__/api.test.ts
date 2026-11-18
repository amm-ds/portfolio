import { describe, expect, it, vi, afterEach } from "vitest";
import { getMetrics, getProjectHeadlines, getProjects, getStory } from "../api";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status });
}

afterEach(() => vi.unstubAllGlobals());

describe("getProjects", () => {
  const payload = [{
    id: "01-rag-agent",
    title: "RAG Agent",
    domain: "NLP",
    topic: "Agentic AI & LLM",
    techniques: ["RAG"],
    data: "docs",
    status: "flagship",
    order: 1,
  }];

  it("fetches validated JSON and forwards the abort signal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(getProjects(controller.signal)).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/projects", { signal: controller.signal });
  });

  it("rejects malformed nested project fields", async () => {
    const malformed = structuredClone(payload);
    malformed[0].techniques = [null as unknown as string];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(malformed)));
    await expect(getProjects()).rejects.toThrow("invalid response contract");
  });

  it("throws on non-OK responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 500 })));
    await expect(getProjects()).rejects.toThrow("500");
  });
});

describe("getProjectHeadlines", () => {
  it("fetches the compact headline index", async () => {
    const payload = { "01-rag-agent": { metric: "faithfulness", value: 0.83 } };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getProjectHeadlines()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/projects/headlines", { signal: undefined });
  });

  it("rejects malformed nested headline values", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      "01-rag-agent": { metric: "faithfulness", value: "0.83" },
    })));
    await expect(getProjectHeadlines()).rejects.toThrow("invalid response contract");
  });
});

describe("getStory", () => {
  it("rejects malformed nested sections instead of returning them as a story", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      project_id: "01-rag-agent",
      sections: [{
        id: "background",
        title: "Background",
        text_md: "Context.",
        figures: [null],
        metrics_keys: [],
      }],
    })));
    await expect(getStory("01-rag-agent")).rejects.toThrow("invalid response contract");
  });
});

describe("getMetrics", () => {
  it("returns metrics JSON on success", async () => {
    const metrics = { baseline: { f1: 0.5 } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(metrics)));
    await expect(getMetrics("01-rag-agent")).resolves.toEqual(metrics);
  });

  it("accepts payloads with non-record top-level values (02 full-panel shape)", async () => {
    const metrics = {
      _meta: { source: "reports_m5_full/metrics.json" },
      candidates: [{ model: "lightgbm", wrmsse: 0.62 }],
      pooled_strategy: "bottom_up",
      protocol: "temporal holdout",
      test: { wrmsse: 0.61 },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(metrics)));
    await expect(getMetrics("02-demand-forecasting")).resolves.toEqual(metrics);
  });

  it("still rejects a non-object payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([{ f1: 0.5 }])));
    await expect(getMetrics("01-rag-agent")).rejects.toThrow("invalid response contract");
  });

  it("returns null on 404 (pipeline not run yet)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not found", { status: 404 })));
    await expect(getMetrics("05-ml-pipeline-churn")).resolves.toBeNull();
  });

  it("rethrows other errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("err", { status: 500 })));
    await expect(getMetrics("01-rag-agent")).rejects.toThrow("500");
  });
});
