import { Fragment, type ReactNode } from "react";

/** "a · b · c" → parts joined by an accent-tinted "·" separator, so the
 * descriptor text can stay blue while the separators read green. */
function accented(text: string): ReactNode {
  if (!text.includes("·")) return text;
  return text.split("·").map((part, i) => (
    <Fragment key={i}>
      {i > 0 && <span className="study-sep">·</span>}
      {part}
    </Fragment>
  ));
}

/** Shared card layout for the projects index — demo cards and experiment
 * cards render the exact same structure: title; a one-line domain/dataset
 * descriptor (blue, accent separators); two side-by-side muted text blocks —
 * left "what it does", right "what it achieves" (experiment cards only; demo
 * cards carry the left block alone); the brief result line (experiment cards
 * only); and exactly four tags. Callers wrap it in their link. */
export function StudyCard({
  title,
  subtitle,
  does,
  achieves,
  result,
  tags,
}: {
  title: string;
  /** One-line domain/dataset descriptor (mono, blue). */
  subtitle?: string;
  /** "What it does" block (left column). */
  does?: string;
  /** "What it achieves" block (right column); experiment cards only. */
  achieves?: string;
  /** "Brief results" line (mono, accent); experiment cards only — hidden
   * while a live metric has not loaded yet. */
  result?: ReactNode;
  /** Exactly four short tags (blue). */
  tags: string[];
}) {
  return (
    <>
      <h3>{title}</h3>
      {subtitle && <p className="study-sub">{accented(subtitle)}</p>}
      {(does || achieves) && (
        <div className="study-cols">
          {does && <p className="study-does">{does}</p>}
          {achieves && <p className="study-achieves">{achieves}</p>}
        </div>
      )}
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
