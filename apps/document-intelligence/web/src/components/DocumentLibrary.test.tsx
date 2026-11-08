import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Workbench } from "../workbench/useWorkbench";
import { documentRecord, otherDocument, partialAnalysisResponse } from "../test/fixtures";
import { DocumentLibrary } from "./DocumentLibrary";

function makeWorkbench(overrides: Partial<Workbench> = {}): Workbench {
  return {
    documents: [documentRecord, otherDocument],
    selectedId: documentRecord.id,
    libraryLoading: false,
    busy: null,
    analyses: { [otherDocument.id]: partialAnalysisResponse },
    refreshLibrary: vi.fn(),
    upload: vi.fn().mockResolvedValue(undefined),
    selectDocument: vi.fn(),
    reanalyze: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as Workbench;
}

describe("DocumentLibrary", () => {
  it("shows document cards with status and page progress", () => {
    render(<DocumentLibrary workbench={makeWorkbench()} />);
    expect(screen.getByText("analysis-multipage.pdf")).toBeInTheDocument();
    expect(screen.getByText("regional-report.pdf")).toBeInTheDocument();
    expect(screen.getAllByText("completed")).toHaveLength(1);
    expect(screen.getAllByText("processing")).toHaveLength(1);
    expect(screen.getByText("2 pages")).toBeInTheDocument();
    expect(screen.getByText("1/2 pages processed")).toBeInTheDocument();
  });

  it("describes failed and queued documents honestly", () => {
    render(
      <DocumentLibrary
        workbench={makeWorkbench({
          documents: [
            { ...documentRecord, id: "a", status: "failed" },
            { ...documentRecord, id: "b", status: "uploaded", page_count: null },
          ],
        })}
      />,
    );
    expect(screen.getByText("analysis failed")).toBeInTheDocument();
    expect(screen.getByText("queued for analysis")).toBeInTheDocument();
  });

  it("selects a document and reanalyzes from the card actions", async () => {
    const user = userEvent.setup();
    const selectDocument = vi.fn();
    const reanalyze = vi.fn();
    render(<DocumentLibrary workbench={makeWorkbench({ selectDocument, reanalyze })} />);
    await user.click(screen.getByText("regional-report.pdf"));
    expect(selectDocument).toHaveBeenCalledWith(otherDocument.id);
    const buttons = screen.getAllByRole("button", { name: "Reanalyze" });
    await user.click(buttons[1]); // regional-report.pdf is the second card
    expect(reanalyze).toHaveBeenCalledWith(otherDocument.id);
  });

  it("rejects non-PDF uploads before hitting the API", async () => {
    const upload = vi.fn();
    render(<DocumentLibrary workbench={makeWorkbench({ upload })} />);
    const input = screen.getByLabelText(/Upload document PDF/);
    fireEvent.change(input, { target: { files: [new File(["data"], "notes.txt", { type: "text/plain" })] } });
    expect(screen.getByText(/Choose a PDF file/)).toBeInTheDocument();
    expect(upload).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { files: [new File(["%PDF"], "report.pdf", { type: "application/pdf" })] } });
    expect(upload).toHaveBeenCalledTimes(1);
  });

  it("offers committed fixtures with honest provenance", async () => {
    const user = userEvent.setup();
    render(<DocumentLibrary workbench={makeWorkbench()} />);
    await user.click(screen.getByText("Load a committed test fixture"));
    expect(screen.getByText(/not live-model accuracy/)).toBeInTheDocument();
    expect(screen.getByText("Multipage report · 2 pages")).toBeInTheDocument();
    expect(screen.getByText("CV")).toBeInTheDocument();
    expect(screen.getByText("Contract")).toBeInTheDocument();
  });

  it("shows an actionable empty state", () => {
    render(<DocumentLibrary workbench={makeWorkbench({ documents: [] })} />);
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByText(/Upload a PDF or load a fixture/)).toBeInTheDocument();
  });

  it("refreshes from the header button", async () => {
    const user = userEvent.setup();
    const refreshLibrary = vi.fn();
    render(<DocumentLibrary workbench={makeWorkbench({ refreshLibrary })} />);
    await user.click(screen.getByRole("button", { name: "Refresh document library" }));
    expect(refreshLibrary).toHaveBeenCalled();
  });
});
