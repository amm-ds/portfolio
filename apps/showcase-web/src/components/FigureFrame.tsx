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
}: {
  projectId: string;
  name: string;
  caption?: FigureCaption | string | null;
}) {
  const [loaded, setLoaded] = useState(false);
  const captionText =
    caption == null ? null : typeof caption === "string" ? caption : formatFigureCaption(caption);
  return (
    <figure className="figure-frame">
      <div className={`frame-wrap${loaded ? " loaded" : ""}`}>
        {!loaded && (
          <div className="frame-skeleton" aria-hidden="true">
            <span>loading…</span>
          </div>
        )}
        <span className="frame-label">$ {name}</span>
        <iframe
          src={figureUrl(projectId, name)}
          title={`Figure: ${name}`}
          loading="lazy"
          onLoad={() => setLoaded(true)}
        />
      </div>
      {captionText && <figcaption className="figure-caption">{captionText}</figcaption>}
    </figure>
  );
}
