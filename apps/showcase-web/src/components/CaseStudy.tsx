import { Fragment } from "react";
import type { Metrics, ProjectStoryData } from "../api";
import { glossaryEntryBySlug } from "../lib/glossary";
import { glossaryTermsInMarkdown } from "../lib/markdown";
import { useScrollSpy } from "../hooks/useScrollSpy";
import { GlossaryCard } from "./GlossaryCard";
import { KeyConceptsCard } from "./KeyConceptsCard";
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
  // Precompute which section owns each glossary term's first link. This is a
  // local, render-safe derivation: React Strict Mode may discard a render, so
  // child renderers never mutate shared link state.
  const seenGlossary = new Set<string>();
  const linkedTermsBySection = story.sections.map((section) => {
    const owned = new Set<string>();
    for (const slug of glossaryTermsInMarkdown(section.text_md)) {
      if (seenGlossary.has(slug)) continue;
      seenGlossary.add(slug);
      owned.add(slug);
    }
    return owned;
  });
  // The story's vocabulary, in first-use order, for the Background glossary
  // card. Capped: a reference, not a wall.
  const storyGlossary = [...seenGlossary]
    .slice(0, 10)
    .map((slug) => glossaryEntryBySlug(slug))
    .filter((e) => e !== undefined);

  return (
    <div className="story-layout">
        <nav className="rail" aria-label="Case study sections">
          <span className="rail-label">index</span>
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
            <Fragment key={s.id}>
              <StorySection
                projectId={projectId}
                section={s}
                index={i}
                metrics={metrics}
                figureCaptions={story.figure_captions}
                linkedTerms={linkedTermsBySection[i]}
              />
              {s.id === "background" && (
                <>
                  <KeyConceptsCard items={story.key_concepts ?? []} />
                  <GlossaryCard terms={storyGlossary} />
                </>
              )}
            </Fragment>
          ))}
          <RoadmapBlock roadmap={story.roadmap} />
        </div>
    </div>
  );
}
