import type React from "react";
import type { RoadmapItemData } from "../api";
import { Card } from "./Card";

/** Display label for a milestone: the title (roadmap labels wrap — nothing is
 * truncated). Exported for tests. */
export function shortMilestone(text: string): string {
  return text.trim();
}

/**
 * Story roadmap: a visual timeline of shipped work. Visitors see finalized
 * steps only — `shipped` milestones render as nodes on a horizontal progress
 * line (accent-filled dot) with the card title as the visible label and the
 * detail as hover text. `next`/`blocked` cards stay authored in story.yaml
 * (owner decision 2026-11-19) but are not rendered here. Renders nothing when
 * no milestone is shipped yet.
 */
export function RoadmapBlock({ roadmap }: { roadmap: RoadmapItemData[] | undefined }) {
  const shipped = roadmap?.filter((r) => r.status === "shipped") ?? [];
  if (shipped.length === 0) return null;

  return (
    <Card className="roadmap">
      <div className="roadmap-head">
        <h2 className="roadmap-title">roadmap</h2>
      </div>
      <ol className="roadmap-track" style={{ "--n": shipped.length } as React.CSSProperties}>
        {shipped.map((r, i) => (
          <li
            key={i}
            className={`roadmap-node ${r.status}`}
            title={`${r.title} ${r.detail}`}
          >
            <span className="roadmap-dot" aria-label={r.status} role="img" />
            <span className="roadmap-label">{shortMilestone(r.title)}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
