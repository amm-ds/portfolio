import type { RoadmapItemData } from "../api";
import { Card } from "./Card";

const MARKS: Record<RoadmapItemData["status"], { mark: string; className: string }> = {
  delivered: { mark: "✓", className: "delivered" },
  remaining: { mark: "○", className: "remaining" },
  deferred: { mark: "⊘", className: "deferred" },
};

/**
 * Story roadmap: delivered work under "Delivered", open forward work and
 * consciously parked items under "What's next". Renders nothing when the
 * story has no roadmap yet.
 */
export function RoadmapBlock({ roadmap }: { roadmap: RoadmapItemData[] | undefined }) {
  if (!roadmap || roadmap.length === 0) return null;
  const delivered = roadmap.filter((r) => r.status === "delivered");
  const remaining = roadmap.filter((r) => r.status === "remaining");
  const deferred = roadmap.filter((r) => r.status === "deferred");
  const next = [...remaining, ...deferred];

  return (
    <Card className="roadmap">
      <h2 className="roadmap-title">roadmap</h2>
      {delivered.length > 0 && (
        <div className="roadmap-group">
          <h3>delivered</h3>
          <ul>
            {delivered.map((r, i) => (
              <li key={i}>
                <span className="roadmap-mark delivered" aria-label="delivered">
                  {MARKS.delivered.mark}
                </span>
                {r.text}
              </li>
            ))}
          </ul>
        </div>
      )}
      {next.length > 0 && (
        <div className="roadmap-group">
          <h3>what's next</h3>
          <ul>
            {next.map((r, i) => (
              <li key={i}>
                <span
                  className={`roadmap-mark ${MARKS[r.status].className}`}
                  aria-label={r.status}
                >
                  {MARKS[r.status].mark}
                </span>
                {r.text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
