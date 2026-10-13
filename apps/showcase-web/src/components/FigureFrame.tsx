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

function formatCaption(c: FigureCaption): string {
  return `fig :: ${c.sectionId} · ${c.index}/${c.total} — ${c.sectionTitle}`;
}

/**
 * A project figure embedded as a full HTML page in a responsive frame:
 * terminal-style border, mono corner label, dark loading skeleton until the
 * iframe's onLoad fires, and an optional caption bar derived from story context.
 */
export function FigureFrame({
  projectId,
  name,
  caption,
}: {
  projectId: string;
  name: string;
  caption?: FigureCaption;
}) {
  const [loaded, setLoaded] = useState(false);
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
      {caption && <figcaption className="figure-caption">{formatCaption(caption)}</figcaption>}
    </figure>
  );
}
