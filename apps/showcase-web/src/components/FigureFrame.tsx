import { useState } from "react";
import { figureUrl } from "../api";

export interface FigureCaption {
  /** Canonical story section id, e.g. "results". */
  sectionId: string;
  /** 1-based position within the section. */
  index: number;
  total: number;
  sectionTitle: string;
}

export function formatFigureCaption(c: FigureCaption): string {
  return `fig :: ${c.sectionId} · ${c.index}/${c.total} — ${c.sectionTitle}`;
}

/**
 * HTML-iframe figure embed (fallback path): terminal-style border, mono
 * corner label, dark loading skeleton until onLoad. `caption` may be a
 * structured story caption or a preformatted string.
 */
export function FigureFrame({
  projectId,
  name,
  caption,
  aspectRatio,
}: {
  projectId: string;
  name: string;
  caption?: FigureCaption | string | null;
  /** Authored width / height; invalid values use the responsive CSS default. */
  aspectRatio?: number;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const captionText =
    caption == null ? null : typeof caption === "string" ? caption : formatFigureCaption(caption);
  const validAspectRatio =
    typeof aspectRatio === "number" && Number.isFinite(aspectRatio) && aspectRatio > 0
      ? aspectRatio
      : undefined;
  return (
    <figure className="figure-frame">
      <div
        className={`frame-wrap${loaded ? " loaded" : ""}${failed ? " failed" : ""}`}
        style={validAspectRatio === undefined ? undefined : { aspectRatio: validAspectRatio }}
      >
        {!loaded && !failed && (
          <div className="frame-skeleton" aria-hidden="true">
            <span>loading…</span>
          </div>
        )}
        <span className="frame-label">&gt; {name}</span>
        {failed ? (
          <p className="frame-error" role="alert">
            Unable to load figure <strong>{name}</strong>. Try the data table or reload the page.
          </p>
        ) : (
          <iframe
            src={figureUrl(projectId, name)}
            title={`Figure: ${name}`}
            sandbox="allow-scripts allow-same-origin"
            loading="lazy"
            onLoad={() => setLoaded(true)}
            onErrorCapture={() => setFailed(true)}
          />
        )}
      </div>
      {captionText && <figcaption className="figure-caption">{captionText}</figcaption>}
    </figure>
  );
}
