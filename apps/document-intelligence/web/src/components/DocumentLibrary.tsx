import { useRef, useState } from "react";
import type { AnalysisProgress, DocumentRecord } from "../api/types";
import type { Workbench } from "../workbench/useWorkbench";
import { formatDateTime, LoadingState, StatusBadge } from "./ui";

const fixtures = [
  {
    filename: "analysis-multipage.pdf",
    label: "Multipage report · 2 pages",
    description: "Per-page summaries, entities, topics, and cited conversation.",
  },
  {
    filename: "prompt-injection.pdf",
    label: "Prompt injection",
    description: "Untrusted prompt text is ignored; cited analysis remains grounded.",
  },
  {
    filename: "cv.pdf",
    label: "CV",
    description: "A people-focused page with typed source mentions.",
  },
  {
    filename: "report.pdf",
    label: "Report",
    description: "Cited key points, entities, and topics.",
  },
  {
    filename: "contract.pdf",
    label: "Contract",
    description: "Organizations, people, and evidence-backed topics.",
  },
  {
    filename: "unlabeled.pdf",
    label: "Unlabeled notes",
    description: "General page analysis without a predefined document template.",
  },
] as const;

function progressLine(document: DocumentRecord, progress: AnalysisProgress | null): string {
  if (document.status === "failed") return "analysis failed";
  if (document.status === "processing" || document.status === "uploaded") {
    if (progress && progress.page_count > 0) {
      return `${progress.processed_pages + progress.failed_pages}/${progress.page_count} pages processed`;
    }
    return document.status === "uploaded" ? "queued for analysis" : "analyzing…";
  }
  if (document.page_count) return `${document.page_count} pages`;
  return "PDF";
}

export function DocumentLibrary({ workbench }: { workbench: Workbench }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const { documents, selectedId, busy } = workbench;

  const upload = async (file: File) => {
    setLocalError(null);
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setLocalError("Choose a PDF file. Other file types are not accepted.");
      return;
    }
    if (file.size === 0 || file.size > 10_000_000) {
      setLocalError("PDF must be non-empty and no larger than 10 MB.");
      return;
    }
    await workbench.upload(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  const loadFixture = async (filename: string) => {
    setLocalError(null);
    try {
      const response = await fetch(`/fixtures/${filename}`);
      if (!response.ok) throw new Error("Fixture unavailable");
      const blob = await response.blob();
      await upload(new File([blob], filename, { type: "application/pdf" }));
    } catch {
      setLocalError(`Could not load ${filename}. Start Vite from apps/document-intelligence/web.`);
    }
  };

  return (
    <aside className="library" aria-label="Document library">
      <div className="library__heading">
        <div>
          <span className="eyebrow">/library</span>
          <h2>Documents</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={() => void workbench.refreshLibrary()}
          disabled={workbench.libraryLoading}
          aria-label="Refresh document library"
          title="Refresh library"
        >
          ↻
        </button>
      </div>

      <div className="upload-block">
        <input
          ref={inputRef}
          id="pdf-upload"
          className="sr-only"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
          }}
        />
        <label htmlFor="pdf-upload" className={`upload-dropzone ${busy === "upload" ? "is-busy" : ""}`}>
          <span className="upload-dropzone__icon" aria-hidden="true">↑</span>
          <strong>{busy === "upload" ? "Uploading PDF…" : "Upload document PDF"}</strong>
          <span>Born-digital · max 10 MB</span>
        </label>
        {localError ? <p className="inline-error" role="alert">{localError}</p> : null}
        <details className="fixtures">
          <summary>Load a committed test fixture</summary>
          <p>
            Offline synthetic fixtures only. Deterministic analysis is a functional baseline,
            <strong> not live-model accuracy</strong>.
          </p>
          <div className="fixture-list">
            {fixtures.map((fixture) => (
              <button
                type="button"
                key={fixture.filename}
                className="fixture-button"
                disabled={busy !== null}
                onClick={() => void loadFixture(fixture.filename)}
              >
                <span>{fixture.label}</span>
                <small>{fixture.description}</small>
              </button>
            ))}
          </div>
          <code>apps/document-intelligence/web/public/fixtures/</code>
        </details>
      </div>

      <div className="library__list" aria-live="polite" aria-busy={workbench.libraryLoading}>
        {workbench.libraryLoading && !documents ? <LoadingState label="Loading documents…" /> : null}
        {!workbench.libraryLoading && documents?.length === 0 ? (
          <div className="library-empty">
            <strong>No documents yet</strong>
            <p>Upload a PDF or load a fixture to create the first analysis job.</p>
          </div>
        ) : null}
        <ul>
          {(documents ?? []).map((document) => {
            const progress = workbench.analyses[document.id]?.progress ?? null;
            const active =
              document.status === "uploaded" || document.status === "processing";
            return (
              <li key={document.id} className={`document-card ${selectedId === document.id ? "is-selected" : ""}`}>
                <button
                  type="button"
                  className="document-card__select"
                  onClick={() => workbench.selectDocument(document.id)}
                  aria-current={selectedId === document.id ? "true" : undefined}
                >
                  <span className="document-card__topline">
                    <span className="document-card__name">{document.filename}</span>
                    <StatusBadge status={document.status} />
                  </span>
                  <span className="document-card__meta">
                    {active ? (
                      <span className="document-card__progress">
                        <span className="pulse-dot" aria-hidden="true" />
                        {progressLine(document, progress)}
                      </span>
                    ) : (
                      progressLine(document, progress)
                    )}
                  </span>
                  <span className="document-card__meta">{formatDateTime(document.updated_at)}</span>
                </button>
                <button
                  type="button"
                  className="button button--small document-card__reanalyze"
                  disabled={busy !== null}
                  title={`Reanalyze ${document.filename}`}
                  onClick={() => void workbench.reanalyze(document.id)}
                >
                  {busy === "reanalyze" ? "Queueing…" : "Reanalyze"}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
