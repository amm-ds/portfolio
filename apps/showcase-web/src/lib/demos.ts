/** Offline fallback for the projects-page demos block, rendered only when the
 * demo registry endpoint (`GET /demos`) is unreachable. The live list comes
 * from the registry; keep the cards here in sync with the published demos. */
export interface Demo {
  id: string;
  title: string;
  line: string;
  status: "coming soon" | "live";
  /** Target route once live; undefined while the demo is a placeholder. */
  href?: string;
}

export const DEMOS: Demo[] = [
  {
    id: "churn-sandbox",
    title: "churn threshold sandbox",
    line: "Move the alarm threshold and the false-alarm cost — watch the optimal cutoff and the saved budget change on a real churn model.",
    status: "live",
    href: "/demos/churn-sandbox",
  },
];

export const DEMOS_INTRO = "play with the live systems behind the experiments";
