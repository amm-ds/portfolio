import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { documentRecord, pageTwoEvidence, resolvedEvidence } from "../test/fixtures";
import { PdfViewer } from "./PdfViewer";

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

const noop = () => {};

function renderViewer(overrides: Partial<Parameters<typeof PdfViewer>[0]> = {}) {
  return render(
    <PdfViewer
      document={documentRecord}
      content={new ArrayBuffer(8)}
      selectedPage={1}
      pageCount={2}
      onSelectPage={noop}
      pageStates={new Map([[1, "completed"]])}
      loading={false}
      {...overrides}
    />,
  );
}

describe("PdfViewer controlled page rendering", () => {
  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as CanvasRenderingContext2D);
  });

  it("renders only the selected page and labels it", async () => {
    renderViewer({ selectedPage: 2 });
    expect(await screen.findByText("page 2")).toBeInTheDocument();
    expect(screen.getByLabelText("Original PDF page 2")).toBeInTheDocument();
    expect(screen.getByLabelText("Go to page")).toHaveValue("2");
    expect(pdf.getPage).toHaveBeenCalledWith(2);
  });

  it("navigates with prev/next buttons and the page selector", async () => {
    const user = userEvent.setup();
    const onSelectPage = vi.fn();
    renderViewer({ onSelectPage });
    expect(await screen.findByLabelText("Original PDF page 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(onSelectPage).toHaveBeenCalledWith(2);
    await user.selectOptions(screen.getByLabelText("Go to page"), "2");
    expect(onSelectPage).toHaveBeenLastCalledWith(2);
  });

  it("renders page chips with analysis state and selection", async () => {
    const onSelectPage = vi.fn();
    renderViewer({
      onSelectPage,
      pageStates: new Map([[1, "completed"], [2, "failed"]]),
    });
    expect(await screen.findByRole("button", { name: "Page 1 · completed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 2 · failed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1 · completed" })).toHaveAttribute("aria-current", "page");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Page 2 · failed" }));
    expect(onSelectPage).toHaveBeenCalledWith(2);
  });

  it("draws the exact resolved bbox on the selected page", async () => {
    renderViewer({ citation: { label: "Key point 1", evidence: resolvedEvidence } });
    expect(await screen.findByText("“Northwind Labs reduced processing time by 32%.”")).toBeInTheDocument();
    const highlight = await screen.findByTestId("evidence-highlight-1");
    expect(parseFloat(highlight.style.left)).toBeCloseTo(82.8);
    expect(parseFloat(highlight.style.top)).toBeCloseTo(82.8);
    expect(parseFloat(highlight.style.width)).toBeCloseTo(124.2);
    expect(screen.getByText("Highlighted on this page")).toBeInTheDocument();
  });

  it("offers a jump when the citation lives on another page", async () => {
    const onSelectPage = vi.fn();
    const user = userEvent.setup();
    renderViewer({ selectedPage: 1, onSelectPage, citation: { label: "Topic citation", evidence: pageTwoEvidence } });
    const jump = await screen.findByRole("button", { name: "Show page 2" });
    await user.click(jump);
    expect(onSelectPage).toHaveBeenCalledWith(2);
    expect(screen.queryByTestId("evidence-highlight-1")).not.toBeInTheDocument();
  });

  it("never draws a highlight for unresolved evidence", async () => {
    renderViewer({
      citation: { label: "Unresolved citation", evidence: { quote: "not in the PDF", page: null, bbox: null, resolved: false } },
    });
    expect(await screen.findByText("No highlight: evidence unresolved")).toBeInTheDocument();
    expect(screen.queryByTestId("evidence-highlight-1")).not.toBeInTheDocument();
  });

  it("shows an honest empty state without a document", () => {
    render(
      <PdfViewer
        document={null}
        content={null}
        selectedPage={1}
        pageCount={0}
        onSelectPage={noop}
        pageStates={new Map()}
        loading={false}
      />,
    );
    expect(screen.getByText("No document selected")).toBeInTheDocument();
  });
});
