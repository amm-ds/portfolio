import type { ReactNode } from "react";

/** One metadata field on a study card: small muted label over its blue value. */
export interface StudyMetaItem {
  /** Small muted label, e.g. "topics". */
  label: string;
  /** Value rendered under the label (blue, mono). */
  value: string;
}

/** Shared card layout for the projects index — demo cards and experiment
 * cards render the same structure: title; metadata fields stacked label over
 * value (topics/data on experiment cards, use case/domain on demo cards); the
 * "what it does" block and, where present, the "what it achieves" block (both
 * optionally carrying a small section label — demo cards title them
 * "description" and "results"); the brief result line (experiment cards
 * only); and exactly four tags. Callers wrap it in their link. */
export function StudyCard({
  title,
  meta,
  does,
  achieves,
  doesLabel,
  achievesLabel,
  result,
  tags,
}: {
  title: string;
  /** Metadata fields, stacked label-over-value (replaces the old inline
   * "a · b" subtitle). */
  meta?: StudyMetaItem[];
  /** "What it does" block (objective + data + approach). */
  does?: string;
  /** "What it achieves" block (the measured result). */
  achieves?: ReactNode;
  /** Small section label above the does block (demo cards: "description"). */
  doesLabel?: string;
  /** Small section label above the achieves block (demo cards: "results"). */
  achievesLabel?: string;
  /** "Brief results" line (mono, accent); experiment cards only — hidden
   * while a live metric has not loaded yet. */
  result?: ReactNode;
  /** Exactly four short tags (blue). */
  tags: string[];
}) {
  const labeled = Boolean(doesLabel || achievesLabel);
  return (
    <>
      <h3>{title}</h3>
      {meta && meta.length > 0 && (
        <div className="study-meta">
          {meta.map((m) => (
            <div className="study-meta-item" key={`${m.label}:${m.value}`}>
              <span className="study-meta-label">{m.label}</span>
              <span className="study-sub">{m.value}</span>
            </div>
          ))}
        </div>
      )}
      {labeled ? (
        <>
          {does && (
            <div className="study-block">
              {doesLabel && <span className="study-block-label">{doesLabel}</span>}
              <p className="study-does">{does}</p>
            </div>
          )}
          {achieves && (
            <div className="study-block">
              {achievesLabel && <span className="study-block-label">{achievesLabel}</span>}
              <p className="study-achieves">{achieves}</p>
            </div>
          )}
        </>
      ) : (
        (does || achieves) && (
          <div className="study-cols">
            {does && <p className="study-does">{does}</p>}
            {achieves && <p className="study-achieves">{achieves}</p>}
          </div>
        )
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
