import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { usePageMeta } from "../seo";

/** Routed evaluation-report page (/projects/:id/report): renders the
 * API-served full-width HTML report inside a same-origin frame so the
 * report's themed markup is sandboxed from the app shell (the same pattern
 * FigureFrame uses for HTML figures). The frame is sized to the report's
 * content height on load. The API also supplies the escaped HTML-source
 * details inside the document, so direct and framed routes share one contract. */
export function ReportView() {
  const { id = "" } = useParams();
  const [sourceHtml, setSourceHtml] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "missing" | "error">("loading");
  const [attempt, setAttempt] = useState(0);

  usePageMeta({
    title: "Evaluation report",
    description: `Full evaluation report for the ${id} experiment — metrics, figures and limits.`,
    noindex: true,
  });

  useEffect(() => {
    let cancelled = false;
    setSourceHtml(null);
    setStatus("loading");
    fetch(`/projects/${id}/report`)
      .then(async (res) => {
        if (res.status === 404) {
          if (!cancelled) setStatus("missing");
          return null;
        }
        if (!res.ok) throw new Error(`report request failed: ${res.status}`);
        return res.text();
      })
      .then((text) => {
        if (!cancelled && text !== null) setSourceHtml(text);
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  if (status === "missing") {
    return (
      <div className="state-box">
        <h1>Report unavailable</h1>
        <p>
          No evaluation report has been published for this project yet — run its
          pipeline to generate one.
        </p>
        <p>
          <Link to={`/projects/${id}`}>← back to the case study</Link>
        </p>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="state-box error" role="alert">
        <h1>Report could not be loaded</h1>
        <p>The evaluation report request failed. Check the API and try again.</p>
        <p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)}>
            Retry
          </button>{" "}
          <Link to={`/projects/${id}`}>← back to the case study</Link>
        </p>
      </div>
    );
  }
  if (sourceHtml === null) return <p className="loading">loading report…</p>;
  return (
    <div className="report-view">
      <iframe
        className="report-frame"
        title={`Evaluation report: ${id}`}
        sandbox="allow-scripts allow-same-origin"
        srcDoc={sourceHtml}
        onLoad={(e) => {
          // same-origin frame: fit the frame to the report's content height
          const frame = e.currentTarget;
          const doc = frame.contentDocument;
          if (doc?.documentElement) {
            frame.style.height = `${doc.documentElement.scrollHeight + 8}px`;
          }
        }}
      />
    </div>
  );
}
