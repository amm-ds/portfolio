import { useState } from "react";
import type { PageAnalysis } from "../api/types";
import type { Workbench } from "../workbench/useWorkbench";
import { EmptyState, formatDateTime, LoadingState, StatusBadge } from "./ui";
import { PageChatMode } from "./PageChatMode";
import { PageEntitiesMode } from "./PageEntitiesMode";
import { PageSummaryMode } from "./PageSummaryMode";
import { PageTopicsMode } from "./PageTopicsMode";

type PageMode = "summary" | "entities" | "topics" | "chat";

const MODES: Array<{ mode: PageMode; label: string }> = [
  { mode: "summary", label: "Summary" },
  { mode: "entities", label: "Entities" },
  { mode: "topics", label: "Topics" },
  { mode: "chat", label: "Conversation" },
];

function modeKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("[role='tab']"));
  const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
  if (current < 0) return;
  event.preventDefault();
  const next =
    event.key === "Home" ? 0 :
    event.key === "End" ? buttons.length - 1 :
    (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
  buttons[next]?.focus();
  buttons[next]?.click();
}

export function PageAnalysisPanel({ workbench }: { workbench: Workbench }) {
  const [mode, setMode] = useState<PageMode>("summary");
  const {
    selectedDocument,
    selectedAnalysis,
    selectedPageAnalysis,
    selectedPage,
    pageCount,
    detailLoading,
  } = workbench;

  if (!selectedDocument) {
    return (
      <section className="analysis-panel panel" aria-labelledby="analysis-heading">
        <PanelHeader />
        <EmptyState title="Analysis idle">
          <p>Select a document to read its per-page analysis.</p>
        </EmptyState>
      </section>
    );
  }

  if (detailLoading && !selectedAnalysis) {
    return (
      <section className="analysis-panel panel" aria-labelledby="analysis-heading">
        <PanelHeader />
        <LoadingState label="Loading page analysis…" />
      </section>
    );
  }

  const page = selectedPageAnalysis;
  const progress = selectedAnalysis?.progress ?? null;
  const analyzer = selectedAnalysis?.analyzer ?? null;
  const pageState: "completed" | "failed" | "pending" = page ? page.status : "pending";

  const canDownloadPage = page?.status === "completed";
  const canDownloadFull = Boolean(selectedAnalysis?.analysis && selectedAnalysis.analysis.pages.length > 0);

  return (
    <section className="analysis-panel panel" aria-labelledby="analysis-heading">
      <PanelHeader />

      <div className="page-meta">
        <div className="page-meta__line">
          <strong>
            Page {selectedPage} of {pageCount}
          </strong>
          <PageStateBadge state={pageState} page={page} />
          {page ? (
            <span className="meta-pills" aria-label="Page content statistics">
              <span className="meta-pill">{formatCount(page.text_chars)} chars</span>
              <span className="meta-pill">{page.image_count} image{page.image_count === 1 ? "" : "s"}</span>
              <span className="meta-pill">{page.table_count} table{page.table_count === 1 ? "" : "s"}</span>
            </span>
          ) : null}
        </div>
        {selectedAnalysis ? (
          <p className="page-meta__timestamps">
            analyzer {analyzer ?? "unknown"}
            {progress ? ` · ${progress.processed_pages}/${progress.page_count} pages processed` : ""}
            {" · updated "}
            {formatDateTime(selectedAnalysis.updated_at)}
          </p>
        ) : (
          <p className="page-meta__timestamps">No analysis yet. The analyzer result appears here as pages complete.</p>
        )}
      </div>

      {page && page.issues.length > 0 ? (
        <div className="page-issues">
          <span className="eyebrow">Validation issues · unresolved evidence is not highlighted</span>
          <ul className="issue-list">
            {page.issues.map((issue, index) => (
              <li key={`${index}-${issue.code}`} className={`issue ${issue.severity === "warning" ? "issue--warning" : ""}`}>
                <div className="issue__topline">
                  <code>{issue.code}</code>
                  <span>{issue.severity}</span>
                </div>
                <p>{issue.message}</p>
                <small>{issue.path}</small>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mode-switch" role="tablist" aria-label="Page analysis modes" tabIndex={-1} onKeyDown={modeKeyDown}>
        {MODES.map((item) => (
          <button
            key={item.mode}
            type="button"
            role="tab"
            id={`mode-tab-${item.mode}`}
            aria-selected={mode === item.mode}
            aria-controls="mode-panel"
            tabIndex={mode === item.mode ? 0 : -1}
            className={mode === item.mode ? "is-active" : ""}
            onClick={() => setMode(item.mode)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        className="analysis-panel__body"
        role="tabpanel"
        id="mode-panel"
        aria-labelledby={`mode-tab-${mode}`}
        tabIndex={0}
      >
        {mode === "chat" ? (
          <PageChatMode
            pageNumber={selectedPage}
            history={workbench.chatHistory(selectedPage)}
            sending={workbench.chatSending}
            error={workbench.chatError}
            onSend={workbench.sendChat}
            onRetry={workbench.retryChat}
            onReveal={workbench.revealCitation}
          />
        ) : !page ? (
          <NoPageState documentStatus={selectedDocument.status} />
        ) : page.status === "failed" ? (
          <div className="panel-error" role="alert">
            <strong>Page {page.page} analysis failed.</strong>
            <span>{page.error ?? "The analyzer did not report an error message."}</span>
          </div>
        ) : mode === "summary" ? (
          <PageSummaryMode page={page} onReveal={workbench.revealCitation} />
        ) : mode === "entities" ? (
          <PageEntitiesMode page={page} onReveal={workbench.revealCitation} />
        ) : (
          <PageTopicsMode page={page} onReveal={workbench.revealCitation} />
        )}
      </div>

      <div className="download-bar" aria-label="Analysis downloads">
        <span className="download-bar__label">Analysis downloads · not the PDF</span>
        <div className="download-bar__buttons">
          <button
            type="button"
            className="button button--small"
            disabled={!canDownloadFull || workbench.downloading !== null}
            title={canDownloadFull ? "Download the full analysis as JSON" : "No completed page analyses yet"}
            onClick={() => void workbench.download("full", "json")}
          >
            {workbench.downloading === "full:json:0" ? "Downloading…" : "Full JSON"}
          </button>
          <button
            type="button"
            className="button button--small"
            disabled={!canDownloadFull || workbench.downloading !== null}
            title={canDownloadFull ? "Download the full analysis as Markdown" : "No completed page analyses yet"}
            onClick={() => void workbench.download("full", "md")}
          >
            {workbench.downloading === "full:md:0" ? "Downloading…" : "Full Markdown"}
          </button>
          <button
            type="button"
            className="button button--small"
            disabled={!canDownloadPage || workbench.downloading !== null}
            title={
              canDownloadPage
                ? `Download the page ${selectedPage} analysis as JSON`
                : `Page ${selectedPage} has no completed analysis yet`
            }
            onClick={() => void workbench.download("page", "json", selectedPage)}
          >
            {workbench.downloading === `page:json:${selectedPage}` ? "Downloading…" : `Page ${selectedPage} JSON`}
          </button>
          <button
            type="button"
            className="button button--small"
            disabled={!canDownloadPage || workbench.downloading !== null}
            title={
              canDownloadPage
                ? `Download the page ${selectedPage} analysis as Markdown`
                : `Page ${selectedPage} has no completed analysis yet`
            }
            onClick={() => void workbench.download("page", "md", selectedPage)}
          >
            {workbench.downloading === `page:md:${selectedPage}` ? "Downloading…" : `Page ${selectedPage} Markdown`}
          </button>
        </div>
      </div>
    </section>
  );
}

function PanelHeader() {
  return (
    <header className="panel__header">
      <div>
        <span className="eyebrow">/analysis · page-analysis-v1</span>
        <h2 id="analysis-heading">Page analysis</h2>
      </div>
    </header>
  );
}

function PageStateBadge({ state, page }: { state: "completed" | "failed" | "pending"; page: PageAnalysis | null }) {
  if (state === "completed") return <StatusBadge status="completed" />;
  if (state === "failed") return <StatusBadge status="failed" />;
  return <span className="status-badge">{page ? "pending" : "no analysis"}</span>;
}

/** Thousands grouping without relying on the environment's ICU data. */
function formatCount(value: number): string {
  return String(value).replaceAll(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function NoPageState({ documentStatus }: { documentStatus: string }) {
  return (
    <div className="mode-empty" role="status">
      {documentStatus === "failed" ? (
        <p className="muted">Document analysis failed. Reanalyze to retry the failed pages.</p>
      ) : documentStatus === "completed" ? (
        <p className="muted">No analysis entry exists for this page.</p>
      ) : (
        <p className="muted">
          Page analysis is still in progress. Partial results appear as the worker completes each page.
        </p>
      )}
    </div>
  );
}
