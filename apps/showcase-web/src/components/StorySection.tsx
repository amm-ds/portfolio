import type { Metrics, StorySectionData } from "../api";
import { renderMarkdown } from "../lib/markdown";
import { SECTION_SUBTITLES } from "../lib/sectionMeta";
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

const EXACT_NUMBERS_HEADING = /^## Exact numbers/im;
const LIMITS_HEADING = /^## Limits/im;

/**
 * Conclusions are a first-class visible section: the narrative (results
 * summary, learnings, limits) renders like any other section, and only the
 * heavy technical record (exact numbers, protocol) lives in the collapsed
 * dropdown. The skeleton authors Limits after Protocol, so it is lifted out
 * of the technical part and rendered with the visible narrative. Stories
 * without the `## Exact numbers` heading fall back to the whole body inside
 * the dropdown.
 */
function splitConclusionsTechnical(md: string): [string, string | null] {
  const m = EXACT_NUMBERS_HEADING.exec(md);
  if (!m || m.index === undefined) return [md, null];
  const visible = md.slice(0, m.index).trimEnd();
  let technical = md.slice(m.index).trim();
  const limitsMatch = LIMITS_HEADING.exec(technical);
  let limits: string | null = null;
  if (limitsMatch && limitsMatch.index !== undefined) {
    // Limits is the final block of the skeleton; everything after the
    // heading (up to the trailing takeaway, already split off) is the limit
    // bullets.
    limits = technical.slice(limitsMatch.index).trim();
    technical = technical.slice(0, limitsMatch.index).trimEnd();
  }
  const visibleAll = limits ? `${visible}\n\n${limits}` : visible;
  return [visibleAll, technical];
}

/** One case-study section: markdown prose + results table left, native plotly figures right. */
export function StorySection({
  projectId,
  section,
  metrics,
  figureCaptions = {},
  linkedTerms,
}: {
  projectId: string;
  section: StorySectionData;
  /** Section position from the parent map; numbering renders in the left
   * rail only, so the section h2 carries the bare title. */
  index: number;
  metrics: Metrics | null;
  /** Story `figure_captions`, keyed by figure name. */
  figureCaptions?: Record<string, string>;
  /** Shared glossary-linked slug set, threaded page-wide by the case study. */
  linkedTerms?: Set<string>;
}) {
  const [proseMd, implication, implicationLabel] = splitBusinessImplication(section.text_md);
  const [visibleMd, technicalMd] =
    section.id === "conclusions" ? splitConclusionsTechnical(proseMd) : [proseMd, null];
  const card =
    implication && implicationLabel ? (
      <BusinessImplication label={implicationLabel}>
        {renderMarkdown(implication, linkedTerms)}
      </BusinessImplication>
    ) : null;
  const figures = section.figures.map((name) => (
    <FigureCard
      key={name}
      pid={projectId}
      name={name}
      caption={figureCaptions[name]}
    />
  ));
  // Legacy conclusions (no skeleton heading) keep the old layout: the card
  // sits above the collapsed body and is not duplicated inside it.
  const cardInBody = !(section.id === "conclusions" && technicalMd === null);
  const main = (
    <div className="story-main">
      <div className="prose">{renderMarkdown(visibleMd, linkedTerms)}</div>
      {cardInBody && card}
      {metrics && <StoryMetricsTable metrics={metrics} metricsKeys={section.metrics_keys} />}
    </div>
  );
  const body = (
    <div className="story-cols">
      {main}
      {section.figures.length > 0 && <div className="story-figs">{figures}</div>}
    </div>
  );

  return (
    <section id={`sec-${section.id}`} className="story-section">
      <h2>{section.title}</h2>
      {SECTION_SUBTITLES[section.id] && (
        <p className="section-subtitle">{SECTION_SUBTITLES[section.id]}</p>
      )}
      {section.id === "conclusions" && technicalMd !== null ? (
        <>
          {/* A first-class section: narrative + takeaway visible; the exact
              numbers and protocol are the extra, collapsed by default. */}
          {body}
          <details className="story-details">
            <summary>Technical details — exact numbers and protocol</summary>
            <div className="prose">{renderMarkdown(technicalMd, linkedTerms)}</div>
          </details>
        </>
      ) : section.id === "conclusions" ? (
        <>
          {/* Legacy conclusions without the skeleton heading: the takeaway
              stays visible; the evidence lives in the collapsed block. */}
          {card}
          <details className="story-details">
            <summary>Technical details — exact numbers and protocol</summary>
            {body}
          </details>
        </>
      ) : (
        body
      )}
    </section>
  );
}
