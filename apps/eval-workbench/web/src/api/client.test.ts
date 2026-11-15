import { describe, expect, it, vi } from "vitest";
import { httpApi } from "./client";
import { FIXTURE_RUNS } from "./fixtures";

describe("HTTP API client", () => {
  it("escapes run identifiers in the detail path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(FIXTURE_RUNS[0]), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await httpApi.run("run/with spaces");

    expect(fetchMock).toHaveBeenCalledWith("/runs/run%2Fwith%20spaces", { signal: undefined });
  });

  it("returns the API's error message for non-2xx responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Run is not available." }), { status: 404 }),
    ));

    await expect(httpApi.run("missing")).rejects.toThrow("Run is not available.");
  });
});
