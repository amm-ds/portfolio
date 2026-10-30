import type { Metrics, StorySectionData } from "../api";
import { renderMarkdown } from "../lib/markdown";
import { BusinessImplication } from "./BusinessImplication";
import { StoryMetricsTable } from "./StoryMetricsTable";
import { FigureCard } from "./FigureCard";

// Story YAML uses a trailing takeaway marker, rendered as its own card. New
// stories use `**In plain terms:**`; legacy ones use `**Business summary:**`.
const BI_MARKER = "**Business summary:**";
const PLAIN_MARKER = "**In plain terms:**";

/**
 * Split off the trailing takeaway paragraph (rendered as its own card) from
 * the rest of the section prose. Prefers `**In plain terms:**` when both
 * markers exist. Sections without a marker return the text unchanged with a
 * null tail.
 */
function splitBusinessImplication(
  md: string,
): [string, string | null, "In plain terms" | "Business summary" | null] {
  const plainIdx = md.lastIndexOf(PLAIN_MARKER);
  const biIdx = md.lastIndexOf(BI_MARKER);
  const idx = plainIdx !== -1 ? plainIdx : biIdx;
  const marker = plainIdx !== -1 ? PLAIN_MARKER : BI_MARKER;
  if (idx === -1) return [md, null, null];
  const tail = md.slice(idx + marker.length).trim();
  if (tail === "") return [md, null, null];
  return [
    md.slice(0, idx).trimEnd(),
    tail,
    plainIdx !== -1 ? "In plain terms" : "Business summary",
  ];
}

/** One case-study section: markdown prose + results table left, native plotly figures right. */
export function StorySection({
  projectId,
  section,
  index,
  metrics,
  figureCaptions = {},
  linkedTerms,
}: {
  projectId: string;
  section: StorySectionData;
  index: number;
  metrics: Metrics | null;
  /** Story `figure_captions`, keyed by figure name. */
  figureCaptions?: Record<string, string>;
  /** Shared glossary-linked slug set, threaded page-wide by the case study. */
  linkedTerms?: Set<string>;
}) {
  const [proseMd, implication, implicationLabel] = splitBusinessImplication(section.text_md);
  const figures = section.figures.map((name) => (
    <FigureCard
      key={name}
      pid={projectId}
      name={name}
      caption={figureCaptions[name]}
    />
  ));
  const body = (
    <div className="story-cols">
      <div className="story-main">
        <div className="prose">{renderMarkdown(proseMd, linkedTerms)}</div>
        {implication && implicationLabel && (
          <BusinessImplication label={implicationLabel}>
            {renderMarkdown(implication, linkedTerms)}
          </BusinessImplication>
        )}
        {metrics && <StoryMetricsTable metrics={metrics} metricsKeys={section.metrics_keys} />}
      </div>
      {section.figures.length > 0 && <div className="story-figs">{figures}</div>}
    </div>
  );

  return (
    <section id={`sec-${section.id}`} className="story-section">
      <h2>
        <span className="rail-num">{String(index + 1).padStart(2, "0")} </span>
        {section.title}
      </h2>
      {section.id === "conclusions" ? (
        <details className="story-details">
          <summary>Technical details, revision notes, and reproduction</summary>
          {body}
        </details>
      ) : (
        body
      )}
    </section>
  );
}
