import type { ReactNode } from "react";
import { renderInlineMarkdown } from "../lib/markdown";

/** One metadata field on a study card: small muted label over its blue value. */
export interface StudyMetaItem {
  /** Small muted label, e.g. "topics". */
  label: string;
  /** Value rendered under the label (blue, mono). */
  value: string;
}

/** Shared card layout for the projects index — demo cards and experiment
 * cards render the same structure: title; metadata fields stacked label over
 * value (topics/data on experiment cards, use case/domain on demo cards);
 * the two content blocks side by side, each carrying a small section label
 * in the same style as the metadata labels (experiment cards label them
 * "description" and "results"; demo cards keep only the "description"
 * block); the measured result as a tag/chip — the demo registry's headline
 * metric or the experiment's live key number, one shared chip design; and
 * exactly four tags. The description/results copy renders inline markdown so
 * an authored **bold** key fact stands out. Callers wrap it in their link. */
export function StudyCard({
  title,
  meta,
  does,
  achieves,
  doesLabel,
  achievesLabel,
  result,
  tags,
  headingLevel = 4,
}: {
  title: string;
  /** Semantic title level; cards nested under experiment rows use h4. */
  headingLevel?: 3 | 4;
  /** Metadata fields, stacked label-over-value (replaces the old inline
   * "a · b" subtitle). */
  meta?: StudyMetaItem[];
  /** "What it does" block (objective + data + approach). */
  does?: string;
  /** "What it achieves" block (the measured result). */
  achieves?: ReactNode;
  /** Small section label above the does block (both card kinds: "description"). */
  doesLabel?: string;
  /** Small section label above the achieves block (experiment cards: "results"). */
  achievesLabel?: string;
  /** Measured result rendered as a tag/chip — the demo registry's headline
   * metric or the experiment's live key number; hidden while a live metric
   * has not loaded yet. */
  result?: ReactNode;
  /** Exactly four short tags (blue). */
  tags: string[];
}) {
  const Title = headingLevel === 3 ? "h3" : "h4";
  return (
    <>
      <Title>{title}</Title>
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
      {(does || achieves) && (
        <div className="study-cols">
          {does && (
            <div className="study-block">
              {doesLabel && <span className="study-block-label">{doesLabel}</span>}
              <p className="study-does">{renderInlineMarkdown(does)}</p>
            </div>
          )}
          {achieves && (
            <div className="study-block">
              {achievesLabel && <span className="study-block-label">{achievesLabel}</span>}
              <p className="study-achieves">
                {typeof achieves === "string" ? renderInlineMarkdown(achieves) : achieves}
              </p>
            </div>
          )}
        </div>
      )}
      {/* the result chip lives in the caller's slot content (CardKeyNumber
          renders nothing until a live metric loads, so an empty slot must
          stay hidden via .study-result:empty) */}
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
