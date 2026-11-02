import type { ReactNode } from "react";

/** Shared card layout for the projects index — demo cards and experiment
 * cards render the exact same structure: title; a one-line domain/dataset
 * descriptor; the "what has been built" line; the "brief results" line; and
 * exactly four tags. Callers wrap it in their link (and may pass a live
 * metric badge as the result). */
export function StudyCard({
  title,
  subtitle,
  built,
  result,
  tags,
}: {
  title: string;
  /** One-line domain/dataset descriptor (mono, muted). */
  subtitle?: string;
  /** "What has been built" line. */
  built?: string;
  /** "Brief results" line (mono, accent); hidden while empty (e.g. a live
   * metric that has not loaded yet). */
  result?: ReactNode;
  /** Exactly four short tags. */
  tags: string[];
}) {
  return (
    <>
      <h3>{title}</h3>
      {subtitle && <p className="study-sub">{subtitle}</p>}
      {built && <p className="study-built">{built}</p>}
      {result && <p className="study-result">{result}</p>}
      <div className="chips">
        {tags.map((t) => (
          <span key={t} className="chip">
            {t}
          </span>
        ))}
      </div>
    </>
  );
}
