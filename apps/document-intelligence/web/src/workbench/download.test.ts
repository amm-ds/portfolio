import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadBlob } from "./download";

describe("downloadBlob", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("defers revoking the object URL so Firefox does not cancel the download", () => {
    // jsdom does not implement the blob-URL statics; the download only needs them mocked.
    Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock-url"), configurable: true });
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadBlob(new Blob(["%PDF-test"], { type: "application/pdf" }), "report.pdf");

    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.advanceTimersByTime(0);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });
});
