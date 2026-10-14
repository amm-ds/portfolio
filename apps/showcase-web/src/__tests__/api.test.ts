import { describe, expect, it, vi, afterEach } from "vitest";
import { getMetrics, getProjects } from "../api";

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
