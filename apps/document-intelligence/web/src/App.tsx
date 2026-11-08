import { DEV_ACTOR, DEV_TENANT } from "./api/client";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { PageAnalysisPanel } from "./components/PageAnalysisPanel";
import { PdfViewer } from "./components/PdfViewer";
import type { PageRenderState } from "./components/PdfViewer";
import { Alert, StatusBadge, ThemeSwitcher } from "./components/ui";
import { useWorkbench } from "./workbench/useWorkbench";

export default function App() {
  const workbench = useWorkbench();
  const { selectedDocument, selectedAnalysis, documents, libraryLoading } = workbench;
  const processing = documents?.filter((item) => item.status === "uploaded" || item.status === "processing").length ?? 0;

  const pageStates = new Map<number, PageRenderState>();
  workbench.sortedPages.forEach((page) => pageStates.set(page.page, page.status));
  for (let page = 1; page <= workbench.pageCount; page += 1) {
    if (!pageStates.has(page)) pageStates.set(page, "pending");
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#document-workbench">Skip to document workbench</a>
      <header className="app-header">
        <div className="brand">
          <span className="terminal-dots" aria-hidden="true"><span /><span /><span /></span>
          <div>
            <h1><span>&gt;</span> document-intelligence</h1>
            <p>page-level document analysis</p>
          </div>
        </div>
        <div className="header-controls">
          <div className="header-metrics" aria-label="Library summary">
            <span><strong>{documents?.length ?? 0}</strong> documents</span>
            <span><strong>{processing}</strong> processing</span>
            <span className={`connection-state ${documents ? "is-online" : ""}`}>
              <i aria-hidden="true" />
              {documents ? "API connected" : libraryLoading ? "Connecting…" : "API unavailable"}
            </span>
          </div>
          <ThemeSwitcher />
        </div>
      </header>

      <div className="app-body">
        <DocumentLibrary workbench={workbench} />
        <main className="document-workbench" id="document-workbench" tabIndex={-1}>
          <div className="workspace-notices">
            {workbench.error ? (
              <Alert tone="error" onDismiss={workbench.clearError}>
                <strong>Request failed.</strong> {workbench.error}
              </Alert>
            ) : null}
            {workbench.notice ? (
              <Alert tone="success" onDismiss={workbench.clearNotice}>
                {workbench.notice}
              </Alert>
            ) : null}
          </div>

          <div className="document-titlebar">
            <div className="document-titlebar__identity">
              {selectedDocument ? (
                <>
                  <StatusBadge status={selectedDocument.status} />
                  <div>
                    <h2>{selectedDocument.filename}</h2>
                    <p>
                      <span title={selectedDocument.id}>{selectedDocument.id.slice(0, 8)}</span>
                      {" · "}SHA {selectedDocument.sha256.slice(0, 12)}…
                      {selectedAnalysis?.progress && selectedAnalysis.progress.page_count > 0
                        ? ` · ${selectedAnalysis.progress.processed_pages + selectedAnalysis.progress.failed_pages}/${selectedAnalysis.progress.page_count} pages`
                        : ""}
                      {workbench.detailLoading ? " · refreshing…" : ""}
                    </p>
                  </div>
                </>
              ) : (
                <div><h2>No active document</h2><p>Upload or select a document to begin.</p></div>
              )}
            </div>
          </div>

          <div className="split-screen">
            <PdfViewer
              document={selectedDocument}
              content={workbench.content}
              selectedPage={workbench.selectedPage}
              pageCount={workbench.pageCount}
              onSelectPage={workbench.selectPage}
              pageStates={pageStates}
              citation={workbench.selectedCitation}
              loading={workbench.detailLoading}
            />
            <PageAnalysisPanel workbench={workbench} />
          </div>
        </main>
      </div>

      <footer className="app-footer">
        <span>Evidence coordinates are parser-resolved by the backend; chat and downloads never edit the analysis.</span>
        <span>{import.meta.env.DEV ? `development identity · ${DEV_TENANT} / ${DEV_ACTOR}` : "authenticated API"}</span>
      </footer>
    </div>
  );
}
