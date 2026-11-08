import { useEffect, useMemo, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { DocumentRecord, Evidence } from "../api/types";
import type { SelectedCitation } from "../workbench/useWorkbench";
import { EmptyState, LoadingState } from "./ui";

GlobalWorkerOptions.workerSrc = workerUrl;

export type PageRenderState = "completed" | "failed" | "pending";

interface HighlightBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface RenderViewport {
  viewBox: Array<number>;
  convertToViewportRectangle: (box: number[]) => number[];
}

function evidenceBox(evidence: Evidence, viewport: RenderViewport): HighlightBox | null {
  if (!evidence.resolved || !evidence.bbox) return null;
  // Backend PyMuPDF boxes use a top-left origin; pdf.js conversion expects PDF
  // user-space boxes with a bottom-left origin. Flip Y before conversion so
  // rotation and nonzero crop-box origins remain viewport-correct.
  const [left, bottom, , top] = viewport.viewBox;
  const pageHeight = top - bottom;
  const [x0, y0, x1, y1] = evidence.bbox;
  const pdfBox: [number, number, number, number] = [
    left + x0,
    bottom + pageHeight - y1,
    left + x1,
    bottom + pageHeight - y0,
  ];
  const [vx0, vy0, vx1, vy1] = viewport.convertToViewportRectangle(pdfBox);
  return {
    left: Math.min(vx0, vx1),
    top: Math.min(vy0, vy1),
    width: Math.abs(vx1 - vx0),
    height: Math.abs(vy1 - vy0),
  };
}

export function PdfViewer({
  document,
  content,
  selectedPage,
  pageCount,
  onSelectPage,
  pageStates,
  citation = null,
  loading,
}: {
  document: DocumentRecord | null;
  content: ArrayBuffer | null;
  selectedPage: number;
  pageCount: number;
  onSelectPage: (page: number) => void;
  pageStates: Map<number, PageRenderState>;
  citation?: SelectedCitation | null;
  loading: boolean;
}) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [scale, setScale] = useState(1.15);
  const [rendering, setRendering] = useState(false);
  const [pageViewport, setPageViewport] = useState<RenderViewport | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setPdf(null);
    setPdfError(null);
    setPageViewport(null);
    setScale(1.15);
    if (!content) return;

    const task = getDocument({ data: new Uint8Array(content.slice(0)) });
    task.promise
      .then((loaded) => {
        if (!cancelled) setPdf(loaded);
        else void loaded.destroy();
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setPdfError(reason instanceof Error ? reason.message : "The PDF could not be rendered.");
        }
      });
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [content]);

  // Fit the page width on first load.
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    void pdf.getPage(1).then((page) => {
      if (cancelled) return;
      const naturalWidth = page.getViewport({ scale: 1 }).width;
      const available = (viewerRef.current?.clientWidth ?? 0) - 40;
      if (available > 0 && naturalWidth * 1.15 > available) {
        setScale(Math.max(0.45, available / naturalWidth));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [pdf]);

  // Render only the selected page: multipage documents stay fast and each page is crisp.
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    const tasks: RenderTask[] = [];
    setRendering(true);
    const canvas = canvasRef.current;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);

    const render = async () => {
      const page = await pdf.getPage(selectedPage);
      if (cancelled || !canvas) return;
      const cssViewport = page.getViewport({ scale });
      const viewport = page.getViewport({ scale: scale * pixelRatio });
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${Math.floor(cssViewport.width)}px`;
      canvas.style.height = `${Math.floor(cssViewport.height)}px`;
      if (!cancelled) setPageViewport(cssViewport);
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas 2D is unavailable.");
      const task = page.render({ canvasContext: context, viewport });
      tasks.push(task);
      await task.promise;
      if (!cancelled) setRendering(false);
    };

    render().catch((reason: unknown) => {
      if (cancelled || (reason instanceof Error && reason.name === "RenderingCancelledException")) return;
      setPdfError(reason instanceof Error ? reason.message : "A PDF page could not be rendered.");
      setRendering(false);
    });
    return () => {
      cancelled = true;
      tasks.forEach((task) => task.cancel());
    };
  }, [pdf, selectedPage, scale]);

  const pageNumbers = useMemo(
    () => Array.from({ length: Math.max(0, pageCount) }, (_, index) => index + 1),
    [pageCount],
  );
  const evidence = citation?.evidence ?? null;
  const onSelectedPage = Boolean(evidence?.resolved && evidence.page === selectedPage && evidence.bbox);
  const highlight = onSelectedPage && evidence && pageViewport ? evidenceBox(evidence, pageViewport) : null;

  if (!document) {
    return (
      <div className="pdf-panel panel">
        <EmptyState title="No document selected">
          <p>Select a library document to inspect its original PDF and cited evidence.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <section className="pdf-panel panel" aria-labelledby="pdf-heading">
      <header className="panel__header pdf-toolbar">
        <div className="pdf-toolbar__title">
          <span className="eyebrow">/source</span>
          <h2 id="pdf-heading">Original PDF</h2>
        </div>
        <div className="pdf-toolbar__controls">
          <div className="page-nav" aria-label="PDF page navigation">
            <button
              type="button"
              className="icon-button"
              onClick={() => onSelectPage(selectedPage - 1)}
              disabled={selectedPage <= 1}
              aria-label="Previous page"
            >
              ←
            </button>
            <label htmlFor="pdf-page" className="sr-only">Go to page</label>
            <select
              id="pdf-page"
              value={String(selectedPage)}
              onChange={(event) => onSelectPage(Number(event.target.value))}
              disabled={pageCount === 0}
            >
              {pageNumbers.map((page) => (
                <option key={page} value={page}>Page {page} of {pageCount}</option>
              ))}
            </select>
            <button
              type="button"
              className="icon-button"
              onClick={() => onSelectPage(selectedPage + 1)}
              disabled={selectedPage >= pageCount}
              aria-label="Next page"
            >
              →
            </button>
          </div>
          <div className="zoom-control" aria-label="PDF zoom controls">
            <button
              type="button"
              className="icon-button"
              onClick={() => setScale((value) => Math.max(0.45, value - 0.15))}
              disabled={!pdf || scale <= 0.45}
              aria-label="Zoom out PDF"
            >
              −
            </button>
            <output aria-label="PDF zoom level">{Math.round(scale * 100)}%</output>
            <button
              type="button"
              className="icon-button"
              onClick={() => setScale((value) => Math.min(2.05, value + 0.15))}
              disabled={!pdf || scale >= 2.05}
              aria-label="Zoom in PDF"
            >
              +
            </button>
          </div>
        </div>
      </header>

      <div className="page-strip-wrap">
        <div className="page-strip" role="group" aria-label="Pages">
          {pageNumbers.map((page) => {
            const state = pageStates.get(page) ?? "pending";
            return (
              <button
                key={page}
                type="button"
                className="page-chip"
                data-state={state}
                data-selected={selectedPage === page ? "true" : undefined}
                aria-current={selectedPage === page ? "page" : undefined}
                aria-label={`Page ${page} · ${state}`}
                onClick={() => onSelectPage(page)}
              >
                {page}
              </button>
            );
          })}
        </div>
      </div>

      <div className="pdf-filename" title={document.filename}>
        <span aria-hidden="true">PDF</span>
        <strong>{document.filename}</strong>
        <small>{pageCount} pages · SHA {document.sha256.slice(0, 12)}…</small>
      </div>

      {citation ? (
        <div className={`evidence-callout ${onSelectedPage ? "is-resolved" : "is-unresolved"}`}>
          <div>
            <span className="eyebrow">Selected evidence · {citation.label}</span>
            <blockquote>“{evidence?.quote}”</blockquote>
          </div>
          {evidence?.resolved && evidence.page !== null ? (
            evidence.page === selectedPage ? (
              <strong className="evidence-state">Highlighted on this page</strong>
            ) : (
              <button type="button" className="button button--small" onClick={() => onSelectPage(evidence.page ?? 1)}>
                Show page {evidence.page}
              </button>
            )
          ) : (
            <strong className="evidence-warning">No highlight: evidence unresolved</strong>
          )}
        </div>
      ) : (
        <p className="pdf-instruction">
          Select a citation in the page analysis to reveal its exact source quote and bounding box.
        </p>
      )}

      <div
        className="pdf-viewer"
        ref={viewerRef}
        role="region"
        // The viewer scrolls its page canvas; axe scrollable-region-focusable
        // requires keyboard access on the scrollable element itself.
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        aria-label="PDF page viewer"
        aria-busy={loading || rendering || Boolean(content && !pdf && !pdfError)}
      >
        {loading && !content ? <LoadingState label="Loading original PDF…" /> : null}
        {!loading && !content ? (
          <EmptyState title="PDF unavailable">
            <p>The original file could not be loaded. The analysis remains readable.</p>
          </EmptyState>
        ) : null}
        {content && !pdf && !pdfError ? <LoadingState label="Parsing PDF…" /> : null}
        {pdfError ? (
          <div className="pdf-error" role="alert">
            <strong>PDF renderer error</strong>
            <p>{pdfError}</p>
            <p>You can still read the analysis, but no visual evidence claim is made.</p>
          </div>
        ) : null}
        {pdf && !pdfError ? (
          <div className="pdf-page-wrap" data-page={selectedPage}>
            <div className="pdf-page-label">page {selectedPage}</div>
            <div className="pdf-page">
              <canvas ref={canvasRef} role="img" aria-label={`Original PDF page ${selectedPage}`} />
              {highlight && onSelectedPage ? (
                <div
                  className="evidence-highlight"
                  data-testid={`evidence-highlight-${selectedPage}`}
                  style={{
                    left: highlight.left,
                    top: highlight.top,
                    width: highlight.width,
                    height: highlight.height,
                  }}
                  aria-label={`Resolved evidence on page ${selectedPage}`}
                />
              ) : null}
            </div>
            {rendering ? <div className="pdf-render-progress" role="status">Rendering page {selectedPage}…</div> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
