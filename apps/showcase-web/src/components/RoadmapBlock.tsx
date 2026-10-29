import type React from "react";
import type { RoadmapItemData } from "../api";
import { Card } from "./Card";

/** Display label for a milestone: the full text (roadmap nodes wrap — nothing
 * is truncated). Exported for tests. */
export function shortMilestone(text: string): string {
  return text.trim();
}

/**
 * Story roadmap as a visual timeline: one node per milestone on a horizontal
 * progress line (delivered = accent-filled dot, open/deferred = hollow dot),
 * with the full milestone as both the visible label and hover text. Renders
 * nothing when the story has no roadmap yet.
 */
export function RoadmapBlock({ roadmap }: { roadmap: RoadmapItemData[] | undefined }) {
  if (!roadmap || roadmap.length === 0) return null;

  return (
    <Card className="roadmap">
      <div className="roadmap-head">
        <h2 className="roadmap-title">roadmap</h2>
      </div>
      <ol className="roadmap-track" style={{ "--n": roadmap.length } as React.CSSProperties}>
        {roadmap.map((r, i) => (
          <li key={i} className={`roadmap-node ${r.status}`} title={r.text}>
            <span className="roadmap-dot" aria-label={r.status} role="img" />
            <span className="roadmap-label">{shortMilestone(r.text)}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
