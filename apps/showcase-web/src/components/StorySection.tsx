import type { Metrics, StorySectionData } from "../api";
import { renderMarkdown } from "../lib/markdown";
import { BusinessImplication } from "./BusinessImplication";
import { StoryMetricsTable } from "./StoryMetricsTable";
import { FigureCard } from "./FigureCard";

// Story YAML uses `**Business summary:**` as the trailing takeaway marker.
const BI_MARKER = "**Business summary:**";

/**
 * Split off the trailing `**Business summary:** ...` paragraph (rendered
 * as its own card) from the rest of the section prose. Sections without the
 * marker return the text unchanged with a null tail.
 */
function splitBusinessImplication(md: string): [string, string | null] {
  const idx = md.lastIndexOf(BI_MARKER);
  if (idx === -1) return [md, null];
  const tail = md.slice(idx + BI_MARKER.length).trim();
  if (tail === "") return [md, null];
  return [md.slice(0, idx).trimEnd(), tail];
}

/** One case-study section: markdown prose + results table left, native plotly figures right. */
export function StorySection({
  projectId,
  section,
  index,
  metrics,
  figureCaptions = {},
}: {
  projectId: string;
  section: StorySectionData;
  index: number;
  metrics: Metrics | null;
  /** Story `figure_captions`, keyed by figure name. */
  figureCaptions?: Record<string, string>;
}) {
  const [proseMd, implication] = splitBusinessImplication(section.text_md);
  const figures = section.figures.map((name) => (
    <FigureCard
      key={name}
      pid={projectId}
      name={name}
      caption={figureCaptions[name]}
    />
  ));

  return (
    <section id={`sec-${section.id}`} className="story-section">
      <h2>
        <span className="rail-num">{String(index + 1).padStart(2, "0")} </span>
        {section.title}
      </h2>
      <div className="story-cols">
        <div className="story-main">
          <div className="prose">{renderMarkdown(proseMd)}</div>
          {implication && (
            <BusinessImplication>{renderMarkdown(implication)}</BusinessImplication>
          )}
          {metrics && <StoryMetricsTable metrics={metrics} metricsKeys={section.metrics_keys} />}
        </div>
        {section.figures.length > 0 && <div className="story-figs">{figures}</div>}
      </div>
    </section>
  );
}
