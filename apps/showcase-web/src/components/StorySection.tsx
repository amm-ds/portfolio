import type { Metrics, StorySectionData } from "../api";
import { renderMarkdown } from "../lib/markdown";
import { MetricCallouts } from "./MetricCallouts";
import { PlotlyFigure } from "./PlotlyFigure";

/** One case-study section: markdown prose + metric callouts left, native plotly figures right. */
export function StorySection({
  projectId,
  section,
  index,
  metrics,
}: {
  projectId: string;
  section: StorySectionData;
  index: number;
  metrics: Metrics | null;
}) {
  const total = section.figures.length;
  const figures = section.figures.map((name, i) => (
    <PlotlyFigure
      key={name}
      pid={projectId}
      name={name}
      caption={`fig :: ${section.id} · ${i + 1}/${total} — ${section.title}`}
      sectionId={section.id}
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
          <div className="prose">{renderMarkdown(section.text_md)}</div>
          {metrics && <MetricCallouts metrics={metrics} metricsKeys={section.metrics_keys} />}
        </div>
        {total > 0 && <div className="story-figs">{figures}</div>}
      </div>
    </section>
  );
}
