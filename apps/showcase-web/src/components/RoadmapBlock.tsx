import type React from "react";
import type { RoadmapItemData } from "../api";
import { Card } from "./Card";

/** Display label for a milestone: the full text (roadmap nodes wrap — nothing
 * is truncated). Exported for tests. */
export function shortMilestone(text: string): string {
  return text.trim();
}

/**
 * Story roadmap as a visual timeline of shipped work: one node per delivered
 * milestone on a horizontal progress line (accent-filled dot), with the full
 * milestone as both the visible label and hover text. Open or deferred items
 * are authoring state, not visitor content — the published roadmap shows
 * completed milestones only. Renders nothing when nothing is delivered yet.
 */
export function RoadmapBlock({ roadmap }: { roadmap: RoadmapItemData[] | undefined }) {
  const delivered = roadmap?.filter((r) => r.status === "delivered") ?? [];
  if (delivered.length === 0) return null;

  return (
    <Card className="roadmap">
      <div className="roadmap-head">
        <h2 className="roadmap-title">roadmap</h2>
      </div>
      <ol className="roadmap-track" style={{ "--n": delivered.length } as React.CSSProperties}>
        {delivered.map((r, i) => (
          <li key={i} className={`roadmap-node ${r.status}`} title={r.text}>
            <span className="roadmap-dot" aria-label={r.status} role="img" />
            <span className="roadmap-label">{shortMilestone(r.text)}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
