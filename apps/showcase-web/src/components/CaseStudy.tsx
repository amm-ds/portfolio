import type { Metrics, ProjectStoryData } from "../api";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { RoadmapBlock } from "./RoadmapBlock";
import { StorySection } from "./StorySection";

/**
 * Case-study layout: sticky section rail (scroll-spy) + rendered sections,
 * with the roadmap block at the end (after conclusions). Authored summary
 * fields (headline/data_note/limits) stay optional schema only — the summary
 * itself leads the Background section prose.
 */
export function CaseStudy({
  projectId,
  story,
  metrics,
}: {
  projectId: string;
  story: ProjectStoryData;
  metrics: Metrics | null;
}) {
  const ids = story.sections.map((s) => `sec-${s.id}`);
  const active = useScrollSpy(ids);

  return (
    <div className="story-layout">
        <nav className="rail" aria-label="Case study sections">
          {story.sections.map((s, i) => (
            <a
              key={s.id}
              href={`#sec-${s.id}`}
              className={active === `sec-${s.id}` ? "active" : ""}
              aria-current={active === `sec-${s.id}` ? "location" : undefined}
            >
              <span className="rail-num">{String(i + 1).padStart(2, "0")}</span>
              {s.title.toLowerCase()}
            </a>
          ))}
        </nav>
        <div>
          {story.sections.map((s, i) => (
            <StorySection
              key={s.id}
              projectId={projectId}
              section={s}
              index={i}
              metrics={metrics}
              figureCaptions={story.figure_captions}
            />
          ))}
          <RoadmapBlock roadmap={story.roadmap} />
        </div>
    </div>
  );
}
