import type React from "react";
import type { RoadmapItemData } from "../api";
import { Card } from "./Card";

/** Short display label for a milestone: the first sentence (or clause) of the
 * text, truncated to ~60 chars. The full text stays available via the node's
 * title attribute. */
export function shortMilestone(text: string): string {
  const end = text.search(/[.!?]/);
  const first = (end === -1 ? text : text.slice(0, end + 1)).trim();
  return first.length > 60 ? `${first.slice(0, 59).trimEnd()}…` : first;
}

/**
 * Story roadmap as a visual timeline: one node per milestone on a horizontal
 * progress line (delivered = accent-filled dot, open/deferred = hollow dot),
 * short label under each node, full text on hover. A "n/n delivered" counter
 * shows next to the title once everything is delivered. Renders nothing when
 * the story has no roadmap yet.
 */
export function RoadmapBlock({ roadmap }: { roadmap: RoadmapItemData[] | undefined }) {
  if (!roadmap || roadmap.length === 0) return null;
  const delivered = roadmap.filter((r) => r.status === "delivered").length;
  const allDelivered = delivered === roadmap.length;

  return (
    <Card className="roadmap">
      <div className="roadmap-head">
        <h2 className="roadmap-title">roadmap</h2>
        {allDelivered && (
          <span className="roadmap-count">
            {delivered}/{roadmap.length} delivered
          </span>
        )}
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
