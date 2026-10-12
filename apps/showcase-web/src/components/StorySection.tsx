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
  return (
    <section id={`sec-${section.id}`} className="story-section">
      <h2>
        <span className="rail-num">{String(index + 1).padStart(2, "0")} </span>
        {section.title}
      </h2>
      <div className="prose">{renderMarkdown(section.text_md)}</div>
      {metrics && <MetricCallouts metrics={metrics} metricsKeys={section.metrics_keys} />}
      {section.figures.map((name) => (
        <FigureFrame key={name} projectId={projectId} name={name} />
      ))}
    </section>
  );
}
