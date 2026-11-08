import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Workbench } from "../workbench/useWorkbench";
import {
  analysisResponse,
  documentRecord,
  failedPageAnalysis,
  pageOneAnalysis,
  resolvedEvidence,
} from "../test/fixtures";
import { PageAnalysisPanel } from "./PageAnalysisPanel";

function makeWorkbench(overrides: Partial<Workbench> = {}): Workbench {
  return {
    selectedDocument: documentRecord,
    selectedAnalysis: analysisResponse,
    selectedPageAnalysis: pageOneAnalysis,
    selectedPage: 1,
    pageCount: 2,
    detailLoading: false,
    chatHistory: () => [],
    chatSending: false,
    chatError: null,
    sendChat: vi.fn(),
    retryChat: vi.fn(),
    revealCitation: vi.fn(),
    download: vi.fn(),
    downloading: null,
    ...overrides,
  } as unknown as Workbench;
}

describe("PageAnalysisPanel", () => {
  it("shows selected page number, completion state, content counts, and analyzer line", () => {
    render(<PageAnalysisPanel workbench={makeWorkbench()} />);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("1,840 chars")).toBeInTheDocument();
    expect(screen.getByText("1 image")).toBeInTheDocument();
    expect(screen.getByText("0 tables")).toBeInTheDocument();
    expect(screen.getByText(/analyzer fixture-analyzer-v1/)).toBeInTheDocument();
    expect(screen.getByText(/2\/2 pages processed/)).toBeInTheDocument();
  });

  it("renders four modes as tabs and supports arrow-key navigation", async () => {
    const user = userEvent.setup();
    render(<PageAnalysisPanel workbench={makeWorkbench()} />);
    expect(screen.getAllByRole("tab")).toHaveLength(4);
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("tab", { name: "Summary" }));
    fireEvent.keyDown(screen.getByRole("tab", { name: "Summary" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Entities" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "mode-tab-entities");
    // APG: a tabpanel without a guaranteed focusable child stays keyboard-reachable.
    expect(screen.getByRole("tabpanel")).toHaveAttribute("tabindex", "0");
  });

  it("summary mode shows the page summary and cited key points that reveal evidence", async () => {
    const user = userEvent.setup();
    const revealCitation = vi.fn();
    render(<PageAnalysisPanel workbench={makeWorkbench({ revealCitation })} />);
    expect(screen.getByText(pageOneAnalysis.summary.summary)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Reveal source/ })[0]);
    expect(revealCitation).toHaveBeenCalledWith({
      label: "Key point 1 citation 1",
      evidence: resolvedEvidence,
    });
  });

  it("entities mode supports text search and type filtering", async () => {
    const user = userEvent.setup();
    render(<PageAnalysisPanel workbench={makeWorkbench()} />);
    await user.click(screen.getByRole("tab", { name: "Entities" }));
    expect(screen.getAllByText("Northwind Labs").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ada@northwind.dev").length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText("Search entities"), "ada");
    expect(screen.queryByText("Northwind Labs")).not.toBeInTheDocument();
    expect(screen.getAllByText("ada@northwind.dev").length).toBeGreaterThan(0);

    await user.clear(screen.getByLabelText("Search entities"));
    await user.selectOptions(screen.getByLabelText("Filter entities by type"), "email");
    expect(screen.queryByText("Northwind Labs")).not.toBeInTheDocument();
    expect(screen.getAllByText("ada@northwind.dev").length).toBeGreaterThan(0);
  });

  it("topics mode shows labels, rationales, and unresolved evidence honestly", async () => {
    render(<PageAnalysisPanel workbench={makeWorkbench()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Topics" }));
    expect(screen.getByText("process improvement")).toBeInTheDocument();
    expect(screen.getByText("It quantifies a faster operating process.")).toBeInTheDocument();
    const unresolved = screen.getByText("“regional throughput chart”");
    expect(unresolved).toBeInTheDocument();
    const chip = unresolved.closest("li");
    expect(chip?.querySelector("button")).toBeDisabled();
  });

  it("conversation mode renders history, sends new messages, and retries failures", async () => {
    const user = userEvent.setup();
    const sendChat = vi.fn();
    const retryChat = vi.fn();
    render(
      <PageAnalysisPanel
        workbench={makeWorkbench({
          sendChat,
          retryChat,
          chatHistory: (page: number) =>
            page === 1
              ? [
                  { role: "user" as const, content: "What changed?" },
                  { role: "assistant" as const, content: "Processing time fell by 32%.", citations: [resolvedEvidence] },
                ]
              : [],
          chatError: { page: 1, message: "model unavailable" },
        })}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Conversation" }));

    expect(screen.getByText("What changed?")).toBeInTheDocument();
    expect(screen.getByText("Processing time fell by 32%.")).toBeInTheDocument();
    expect(screen.getByText("Answer failed.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(retryChat).toHaveBeenCalledWith(1);

    await user.type(screen.getByLabelText("Ask about page 1"), "Who owns the review?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(sendChat).toHaveBeenCalledWith(1, "Who owns the review?");
  });

  it("shows a failed page honestly with its error message", () => {
    render(
      <PageAnalysisPanel
        workbench={makeWorkbench({ selectedPage: 3, pageCount: 3, selectedPageAnalysis: failedPageAnalysis })}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Page 3 analysis failed.");
    expect(alert).toHaveTextContent("table model timed out");
  });

  it("shows an honest empty state for a missing page", () => {
    render(
      <PageAnalysisPanel workbench={makeWorkbench({ selectedPage: 3, pageCount: 3, selectedPageAnalysis: null })} />,
    );
    expect(screen.getByText("No analysis entry exists for this page.")).toBeInTheDocument();
  });

  it("lists validation issues for the selected page", () => {
    const withIssues = {
      ...pageOneAnalysis,
      issues: [
        { code: "unresolved_evidence", path: "topics[1].evidence[0]", message: "Quote not found on the page", severity: "warning" as const },
      ],
    };
    render(<PageAnalysisPanel workbench={makeWorkbench({ selectedPageAnalysis: withIssues })} />);
    expect(screen.getByText("unresolved_evidence")).toBeInTheDocument();
    expect(screen.getByText("Quote not found on the page")).toBeInTheDocument();
    expect(screen.getByText("topics[1].evidence[0]")).toBeInTheDocument();
  });

  it("disables downloads until analyses exist and labels them as analysis exports", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    render(<PageAnalysisPanel workbench={makeWorkbench({ download })} />);
    expect(screen.getByText("Analysis downloads · not the PDF")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Full JSON" }));
    expect(download).toHaveBeenCalledWith("full", "json");
    await user.click(screen.getByRole("button", { name: "Page 1 Markdown" }));
    expect(download).toHaveBeenCalledWith("page", "md", 1);
  });

  it("disables page downloads until that page analysis exists", () => {
    render(<PageAnalysisPanel workbench={makeWorkbench({ selectedPageAnalysis: null })} />);
    expect(screen.getByRole("button", { name: "Page 1 JSON" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Page 1 Markdown" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Full JSON" })).toBeEnabled();
  });

  it("shows idle and loading states without a document or analysis", () => {
    const { unmount } = render(<PageAnalysisPanel workbench={makeWorkbench({ selectedDocument: null })} />);
    expect(screen.getByText("Analysis idle")).toBeInTheDocument();
    unmount();
    render(
      <PageAnalysisPanel
        workbench={makeWorkbench({ detailLoading: true, selectedAnalysis: null, selectedPageAnalysis: null })}
      />,
    );
    expect(screen.getByText("Loading page analysis…")).toBeInTheDocument();
  });
});
