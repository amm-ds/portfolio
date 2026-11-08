import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { analysisResponse, documentRecord, pageOneAnalysis } from "./test/fixtures";
import App from "./App";

const renderTask = { promise: Promise.resolve(), cancel: vi.fn() };
const page = {
  getViewport: ({ scale }: { scale: number }) => ({
    width: 612 * scale,
    height: 792 * scale,
    viewBox: [0, 0, 612, 792],
    convertToViewportRectangle: (bbox: [number, number, number, number]) => [
      bbox[0] * scale,
      (792 - bbox[1]) * scale,
      bbox[2] * scale,
      (792 - bbox[3]) * scale,
    ],
  }),
  render: vi.fn(() => renderTask),
};
const pdf = {
  numPages: 2,
  getPage: vi.fn().mockResolvedValue(page),
  destroy: vi.fn().mockResolvedValue(undefined),
};

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: () => ({ promise: Promise.resolve(pdf), destroy: vi.fn().mockResolvedValue(undefined) }),
}));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "/pdf-worker.js" }));

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/documents") return jsonResponse([documentRecord]);
      if (url === `/documents/${documentRecord.id}/analysis`) return jsonResponse(analysisResponse);
      if (url === `/documents/${documentRecord.id}/content`) {
        return new Response(new TextEncoder().encode("%PDF-test"), { status: 200 });
      }
      throw new Error(`Unexpected URL: ${url}`);
    }),
  );
}

describe("App workbench", () => {
  it("starts in a loading state and then renders library, PDF, and analysis", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as CanvasRenderingContext2D);
    let resolveDocuments: (value: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url === "/documents") {
          return new Promise<Response>((resolve) => {
            resolveDocuments = resolve;
          });
        }
        if (url === `/documents/${documentRecord.id}/analysis`) {
          return Promise.resolve(jsonResponse(analysisResponse));
        }
        if (url === `/documents/${documentRecord.id}/content`) {
          return Promise.resolve(new Response(new TextEncoder().encode("%PDF-test"), { status: 200 }));
        }
        return Promise.reject(new Error(`Unexpected URL: ${url}`));
      }),
    );

    render(<App />);
    expect(screen.getByText("Loading documents…")).toBeInTheDocument();
    expect(screen.getByText("Connecting…")).toBeInTheDocument();
    expect(screen.queryByText("API unavailable")).not.toBeInTheDocument();

    resolveDocuments(jsonResponse([documentRecord]));
    expect((await screen.findAllByText("analysis-multipage.pdf")).length).toBeGreaterThan(0);
    expect(screen.getByText("API connected")).toBeInTheDocument();
    expect(await screen.findByText(pageOneAnalysis.summary.summary)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Page 1 · completed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 2 · completed" })).toBeInTheDocument();
  });

  it("shows the error banner and idle panels when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("connection refused"))));
    render(<App />);
    expect(await screen.findByText("Request failed.")).toBeInTheDocument();
    expect(screen.getByText(/Cannot reach the document-intelligence API/)).toBeInTheDocument();
    expect(screen.getByText("API unavailable")).toBeInTheDocument();
    expect(screen.getByText("No document selected")).toBeInTheDocument();
    expect(screen.getByText("Analysis idle")).toBeInTheDocument();
  });

  it("keeps terminal identity messaging and the theme switcher", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as CanvasRenderingContext2D);
    stubApi();
    render(<App />);
    expect((await screen.findAllByText("analysis-multipage.pdf")).length).toBeGreaterThan(0);
    expect(screen.getByText("page-level document analysis")).toBeInTheDocument();
    expect(screen.getByText(/development identity · demo \/ developer/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dark/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /light/ })).toBeInTheDocument();
  });
});
