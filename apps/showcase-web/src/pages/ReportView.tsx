import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { usePageMeta } from "../seo";

/** The API serves the project's full evaluation report as a standalone HTML
 * document at /projects/{id}/report. Its embedded stylesheet ships a
 * constrained reading column (body max-width: 1400px, auto margins) — right
 * for a printed artifact, wrong for an in-app page. The in-app report view
 * injects ONE override style into the fetched markup so the report spans the
 * full page width like every other page; this view only — the standalone
 * report, its template and its pipeline stay untouched. */
const FULL_WIDTH_OVERRIDE =
  "<style>body{max-width:none;margin:0;padding:1.25rem 1.5rem;}</style>";

function injectFullWidthOverride(html: string): string {
  if (html.includes("</head>")) return html.replace("</head>", `${FULL_WIDTH_OVERRIDE}</head>`);
  return FULL_WIDTH_OVERRIDE + html;
}

/** Routed evaluation-report page (/projects/:id/report): renders the
 * API-served HTML report inside a same-origin frame so the report's own
 * themed markup is sandboxed from the app shell (the same pattern
 * FigureFrame uses for HTML figures). The frame is sized to the report's
 * content height on load. */
export function ReportView() {
  const { id = "" } = useParams();
  const [html, setHtml] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "missing" | "error">("loading");
  const [attempt, setAttempt] = useState(0);

  usePageMeta({
    title: "Evaluation report",
    description: `Full evaluation report for the ${id} experiment — metrics, figures and limits.`,
    noindex: true,
  });

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
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
        if (!cancelled && text !== null) setHtml(injectFullWidthOverride(text));
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
  if (html === null) return <p className="loading">loading report…</p>;
  return (
    <div className="report-view">
      <iframe
        className="report-frame"
        title={`Evaluation report: ${id}`}
        srcDoc={html}
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
