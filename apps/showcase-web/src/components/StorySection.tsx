import type { Metrics, StorySectionData } from "../api";
import { renderMarkdown } from "../lib/markdown";
import { FigureFrame } from "./FigureFrame";
import { MetricCallouts } from "./MetricCallouts";

/** One case-study section: markdown prose, metric callouts, referenced figures. */
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
  const figures = section.figures;
  const total = figures.length;
  const frames = figures.map((name, i) => (
    <FigureFrame
      key={name}
      projectId={projectId}
      name={name}
      caption={
        total > 0
          ? {
              sectionId: section.id,
              index: i + 1,
              total,
              sectionTitle: section.title,
            }
          : undefined
      }
    />
  ));

  return (
    <section id={`sec-${section.id}`} className="story-section">
      <h2>
        <span className="rail-num">{String(index + 1).padStart(2, "0")} </span>
        {section.title}
      </h2>
      <div className="prose">{renderMarkdown(section.text_md)}</div>
      {metrics && <MetricCallouts metrics={metrics} metricsKeys={section.metrics_keys} />}
      {total === 1 && frames[0]}
      {total >= 2 && <div className="figure-grid">{frames}</div>}
    </section>
  );
}
