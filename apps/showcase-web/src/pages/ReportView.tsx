import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { usePageMeta } from "../seo";
import { injectReportThemeBridge } from "../theme/reportBridge";
import { THEME_STORAGE_KEY, type Theme } from "../theme/useTheme";

/** The active display theme, read from the app shell (`<html data-theme>`,
 * the attribute `applyTheme` writes) and re-read whenever that attribute
 * changes. Reads the DOM attribute rather than a `useTheme` instance so it
 * stays correct no matter which mounted switcher toggled the theme. */
function useActiveTheme(): Theme {
  const read = (): Theme => {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    try {
      return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  };
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return theme;
}

/** Routed evaluation-report page (/projects/:id/report): renders the
 * API-served full-width HTML report inside a same-origin frame so the
 * report's themed markup is sandboxed from the app shell (the same pattern
 * FigureFrame uses for HTML figures). The frame is sized to the report's
 * content height on load. The active theme is injected into the frame as a
 * small bridge (root `data-theme` stamp plus, for light mode, light-surface
 * overrides) rather than by mutating the committed report source, and the
 * bridge is re-injected whenever the theme changes. The API also supplies
 * the escaped HTML-source details inside the document, so direct and framed
 * routes share one contract. */
export function ReportView() {
  const { id = "" } = useParams();
  const [sourceHtml, setSourceHtml] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "missing" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const theme = useActiveTheme();

  const framedHtml = useMemo(
    () => (sourceHtml === null ? null : injectReportThemeBridge(sourceHtml, theme)),
    [sourceHtml, theme],
  );

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
  if (framedHtml === null) return <p className="loading">loading report…</p>;
  return (
    <div className="report-view">
      <iframe
        className="report-frame"
        title={`Evaluation report: ${id}`}
        sandbox="allow-scripts allow-same-origin"
        srcDoc={framedHtml}
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
